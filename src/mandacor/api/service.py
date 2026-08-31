from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from mandacor.application.adjustment_workflow import AdjustmentWorkflow
from mandacor.application.comparison_service import compare_session
from mandacor.application.measurement_wait import (
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.application.sample_capture import CaptureSampleService
from mandacor.application.target_capture import CaptureTargetService
from mandacor.domain.adjustments import (
    AdjustmentComponent,
    AdjustmentHistory,
    AdjustmentLifecycle,
    CompletedAdjustmentTrial,
    PendingAdjustment,
    OperatorTrialStatus,
    VisualResult,
    plan_adjustment,
)
from mandacor.domain.correction import derive_correction_need
from mandacor.domain.diagnosis import diagnose_comparison
from mandacor.domain.pigments import (
    PaintContext,
    PigmentKnowledgeBase,
    build_skylack_knowledge_base,
    evaluate_pigment_candidates,
)
from mandacor.domain.sessions import ColorSession, InvalidSessionStateError, SessionState
from mandacor.infrastructure.storage.pending_adjustment_json import RecoveryFileInvalidError
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentTimeoutError


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class CaptureType(str, Enum):
    TARGET = "target"
    SAMPLE = "sample"
    AFTER = "after"


class OperationStatus(str, Enum):
    PREPARED = "prepared"
    WAITING = "waiting"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class CaptureOperation:
    operation_id: uuid.UUID
    session_id: uuid.UUID
    capture_type: CaptureType
    status: OperationStatus
    created_at: datetime
    request: object
    cancellation: threading.Event = field(default_factory=threading.Event)
    result_measurement_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class InMemorySessionRepository:
    def __init__(self, persistent_repository=None) -> None:
        self._values: dict[uuid.UUID, ColorSession] = {}
        self._lock = threading.RLock()
        self._persistent_repository = persistent_repository
        self.recovery_error: str | None = None
        if persistent_repository is not None:
            try:
                self._values = {
                    item.session_id: item for item in persistent_repository.load_all()
                }
            except RecoveryFileInvalidError:
                self.recovery_error = "SESSION_RECOVERY_FILE_INVALID"

    def save(self, session: ColorSession) -> None:
        with self._lock:
            if self.recovery_error is not None:
                raise RecoveryFileInvalidError(
                    "refusing to overwrite an invalid session recovery file"
                )
            self._values[session.session_id] = session
            if self._persistent_repository is not None:
                self._persistent_repository.save_all(tuple(self._values.values()))

    def get(self, session_id: uuid.UUID) -> ColorSession:
        with self._lock:
            try:
                return self._values[session_id]
            except KeyError as error:
                raise ApiError(404, "SESSION_NOT_FOUND", "session does not exist") from error


class InMemoryOperationRepository:
    ACTIVE = {OperationStatus.PREPARED, OperationStatus.WAITING}

    def __init__(self) -> None:
        self._values: dict[uuid.UUID, CaptureOperation] = {}
        self._lock = threading.RLock()

    def add(self, operation: CaptureOperation) -> None:
        with self._lock:
            if any(
                item.session_id == operation.session_id and item.status in self.ACTIVE
                for item in self._values.values()
            ):
                raise ApiError(
                    409,
                    "CAPTURE_ALREADY_ACTIVE",
                    "another capture operation is active for this session",
                )
            self._values[operation.operation_id] = operation

    def get(self, operation_id: uuid.UUID) -> CaptureOperation:
        with self._lock:
            try:
                return self._values[operation_id]
            except KeyError as error:
                raise ApiError(404, "OPERATION_NOT_FOUND", "operation does not exist") from error

    def update(self, operation: CaptureOperation) -> None:
        with self._lock:
            self._values[operation.operation_id] = operation

    def has_active_for_session(self, session_id: uuid.UUID) -> bool:
        with self._lock:
            return any(
                item.session_id == session_id and item.status in self.ACTIVE
                for item in self._values.values()
            )

    def claim_wait(self, operation_id: uuid.UUID) -> CaptureOperation:
        with self._lock:
            operation = self.get(operation_id)
            if operation.status is not OperationStatus.PREPARED:
                raise ApiError(409, "OPERATION_NOT_WAITABLE", "operation is not prepared")
            operation.status = OperationStatus.WAITING
            return operation

    def cancel_all(self) -> None:
        with self._lock:
            for operation in self._values.values():
                if operation.status in self.ACTIVE:
                    operation.cancellation.set()


class InMemoryAdjustmentRepository:
    def __init__(self) -> None:
        self._values: dict[uuid.UUID, PendingAdjustment | CompletedAdjustmentTrial] = {}
        self._lock = threading.RLock()

    def save(self, adjustment: PendingAdjustment | CompletedAdjustmentTrial) -> None:
        with self._lock:
            self._values[adjustment.adjustment_id] = adjustment

    def get(self, adjustment_id: uuid.UUID):
        with self._lock:
            try:
                return self._values[adjustment_id]
            except KeyError as error:
                raise ApiError(404, "ADJUSTMENT_NOT_FOUND", "adjustment does not exist") from error

    def for_session(self, session_id: uuid.UUID):
        with self._lock:
            return tuple(sorted(
                (item for item in self._values.values() if item.session_id == session_id),
                key=lambda item: item.created_at,
            ))

    def active_pending(self) -> PendingAdjustment | None:
        with self._lock:
            return next(
                (
                    item for item in self._values.values()
                    if isinstance(item, PendingAdjustment)
                    and item.lifecycle is AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER
                ),
                None,
            )

    def history(self, session_id: uuid.UUID) -> AdjustmentHistory:
        completed = tuple(
            item
            for item in self.for_session(session_id)
            if isinstance(item, CompletedAdjustmentTrial)
        )
        return AdjustmentHistory(completed)


class MandacorApiService:
    def __init__(
        self,
        instrument,
        *,
        sessions: InMemorySessionRepository | None = None,
        operations: InMemoryOperationRepository | None = None,
        adjustments: InMemoryAdjustmentRepository | None = None,
        knowledge_base: PigmentKnowledgeBase | None = None,
        pending_repository=None,
        on_adjustment_complete: Callable[[CompletedAdjustmentTrial], None] | None = None,
    ) -> None:
        self.instrument = instrument
        self.sessions = sessions or InMemorySessionRepository()
        self.operations = operations or InMemoryOperationRepository()
        self.adjustments = adjustments or InMemoryAdjustmentRepository()
        self.knowledge_base = knowledge_base or build_skylack_knowledge_base()
        self.pending_repository = pending_repository
        self.on_adjustment_complete = on_adjustment_complete
        self.connected_info = None
        self.recovery_error: str | None = getattr(self.sessions, "recovery_error", None)
        self._instrument_lock = threading.RLock()
        self._adjustment_lock = threading.RLock()
        self._recover_persisted_adjustment()

    def _recover_persisted_adjustment(self) -> None:
        if self.recovery_error is not None:
            return
        if self.pending_repository is None or not hasattr(self.pending_repository, "load"):
            return
        try:
            pending = self.pending_repository.load()
        except RecoveryFileInvalidError as error:
            self.recovery_error = "RECOVERY_FILE_INVALID"
            return
        if pending is None:
            return
        recovered_session = ColorSession(
            session_id=pending.session_id,
            created_at=pending.created_at,
            instrument_serial=pending.instrument_serial,
            target=pending.target,
            sample=pending.before,
            state=SessionState.READY_FOR_COMPARISON,
        )
        self.sessions.save(recovered_session)
        self.adjustments.save(pending)

    def pending_adjustment(self) -> PendingAdjustment | None:
        if self.recovery_error is not None:
            raise ApiError(
                503,
                "RECOVERY_FILE_INVALID",
                "critical pending state could not be read; operator verification is required",
            )
        return self.adjustments.active_pending()

    def instrument_status(self):
        connected = self.instrument.get_status() == "CONNECTED"
        return connected, self.connected_info if connected else None

    def discover(self):
        with self._instrument_lock:
            found = self.instrument.discover_instruments()
            if self.instrument.get_status() != "CONNECTED":
                self.connected_info = None
            return found

    def connect(self, mode: str, host: str | None):
        with self._instrument_lock:
            if mode == "manual":
                if not host:
                    raise ApiError(400, "HOST_REQUIRED", "host is required for manual mode")
                self.connected_info = self.instrument.connect_manual(host)
                return "CONNECTED", self.connected_info, ()
            found = tuple(self.instrument.discover_instruments())
            if len(found) > 1:
                return "MULTIPLE_INSTRUMENTS", None, found
            if len(found) == 1:
                self.connected_info = self.instrument.connect_manual(found[0].ip)
            else:
                self.connected_info = self.instrument.connect_auto()
            return "CONNECTED", self.connected_info, found

    def disconnect(self) -> None:
        with self._instrument_lock:
            self.instrument.disconnect()
            self.connected_info = None

    def require_connected(self):
        connected, info = self.instrument_status()
        if not connected or info is None:
            raise ApiError(503, "INSTRUMENT_DISCONNECTED", "instrument is not connected")
        return info

    def create_session(self) -> ColorSession:
        info = self.require_connected()
        session = ColorSession.create(info.serial)
        self.sessions.save(session)
        return session

    def prepare_capture(self, session_id: uuid.UUID, capture_type: CaptureType):
        info = self.require_connected()
        session = self.sessions.get(session_id)
        if capture_type is CaptureType.TARGET:
            service = CaptureTargetService(self.instrument, instrument_serial=info.serial)
            request = service.prepare_target_capture(session)
        elif capture_type is CaptureType.SAMPLE:
            service = CaptureSampleService(self.instrument, instrument_serial=info.serial)
            try:
                request = service.prepare_sample_capture(session)
            except InvalidSessionStateError as error:
                raise ApiError(409, "TARGET_REQUIRED", str(error)) from error
        else:
            raise ApiError(400, "INVALID_CAPTURE_TYPE", "unsupported capture type")
        operation = CaptureOperation(
            uuid.uuid4(), session_id, capture_type, OperationStatus.PREPARED,
            datetime.now(timezone.utc), request,
        )
        self.operations.add(operation)
        return operation

    def replace_with_latest(
        self, session_id: uuid.UUID, capture_type: CaptureType
    ) -> ColorSession:
        info = self.require_connected()
        session = self.sessions.get(session_id)
        if capture_type not in {CaptureType.TARGET, CaptureType.SAMPLE}:
            raise ApiError(400, "INVALID_CAPTURE_TYPE", "unsupported capture type")
        if self.operations.has_active_for_session(session_id):
            raise ApiError(
                409,
                "CAPTURE_ALREADY_ACTIVE",
                "finish or cancel the active capture before replacing a measurement",
            )
        if self.adjustments.for_session(session_id):
            raise ApiError(
                409,
                "SESSION_MEASUREMENTS_LOCKED",
                "measurements cannot be replaced after an adjustment is registered",
            )
        with self._instrument_lock:
            try:
                latest = self.instrument.get_latest_measurement()
            except InstrumentTimeoutError:
                # A conexão TCP do BYK pode continuar aparecendo como aberta mesmo
                # depois de o aparelho parar de responder. Recriar a conexão uma
                # única vez recupera esse estado sem repetir qualquer medição.
                self.instrument.disconnect()
                self.connected_info = None
                self.connected_info = self.instrument.connect_manual(info.ip)
                latest = self.instrument.get_latest_measurement()
        current = session.target if capture_type is CaptureType.TARGET else session.sample
        if (
            current is not None
            and latest.measurement_id == current.measurement_id
            and (
                latest.guid == current.guid
                if latest.guid is not None and current.guid is not None
                else True
            )
        ):
            raise ApiError(
                409,
                "LATEST_MEASUREMENT_ALREADY_SELECTED",
                "the latest instrument measurement is already selected",
                {"measurement_id": latest.measurement_id},
            )
        try:
            updated = (
                session.replace_target(latest)
                if capture_type is CaptureType.TARGET
                else session.with_sample(latest)
            )
        except InvalidSessionStateError as error:
            raise ApiError(409, "MEASUREMENT_ROLE_CONFLICT", str(error)) from error
        self.sessions.save(updated)
        return updated

    def prepare_adjustment_after(self, adjustment_id: uuid.UUID):
        self.require_connected()
        adjustment = self.adjustments.get(adjustment_id)
        if not isinstance(adjustment, PendingAdjustment):
            raise ApiError(409, "ADJUSTMENT_ALREADY_COMPLETED", "adjustment is completed")
        if adjustment.lifecycle is not AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
            raise ApiError(409, "ADJUSTMENT_NOT_APPLIED", "adjustment is not waiting for AFTER")
        workflow = AdjustmentWorkflow(
            self.instrument, pending_repository=self.pending_repository
        )
        request = workflow.retry_after_capture(adjustment)
        operation = CaptureOperation(
            uuid.uuid4(), adjustment.session_id, CaptureType.AFTER,
            OperationStatus.PREPARED, datetime.now(timezone.utc), request,
        )
        self.operations.add(operation)
        return operation

    def wait_operation(
        self,
        operation_id: uuid.UUID,
        *,
        timeout: float | None,
        poll_interval: float | None,
    ) -> CaptureOperation:
        operation = self.operations.claim_wait(operation_id)
        session = self.sessions.get(operation.session_id)
        try:
            if operation.capture_type is CaptureType.TARGET:
                info = self.require_connected()
                result = CaptureTargetService(
                    self.instrument, instrument_serial=info.serial
                ).capture_target(
                    session, operation.request, timeout=timeout,
                    poll_interval=poll_interval, cancellation=operation.cancellation,
                )
                self.sessions.save(result.session)
            elif operation.capture_type is CaptureType.SAMPLE:
                info = self.require_connected()
                result = CaptureSampleService(
                    self.instrument, instrument_serial=info.serial
                ).capture_sample(
                    session, operation.request, timeout=timeout,
                    poll_interval=poll_interval, cancellation=operation.cancellation,
                )
                self.sessions.save(result.session)
            else:
                workflow = AdjustmentWorkflow(
                    self.instrument, pending_repository=self.pending_repository
                )
                result = workflow.capture_after(
                    session,
                    self.adjustments.history(session.session_id),
                    operation.request,
                    timeout=timeout,
                    poll_interval=poll_interval,
                    cancellation=operation.cancellation,
                )
                if self.on_adjustment_complete is not None:
                    self.on_adjustment_complete(result.trial)
                workflow.acknowledge_completed(result.trial.adjustment_id)
                self.sessions.save(result.session)
                self.adjustments.save(result.trial)
            operation.status = OperationStatus.COMPLETED
            operation.result_measurement_id = result.measurement.measurement_id
        except NewMeasurementTimeoutError as error:
            operation.status = OperationStatus.TIMED_OUT
            operation.error_code = (
                "AFTER_MEASUREMENT_TIMEOUT_ADJUSTMENT_ALREADY_APPLIED"
                if operation.capture_type is CaptureType.AFTER
                else "MEASUREMENT_TIMEOUT"
            )
            operation.error_message = str(error)
            self.operations.update(operation)
            raise ApiError(504, operation.error_code, str(error)) from error
        except MeasurementWaitCancelledError as error:
            operation.status = OperationStatus.CANCELLED
            operation.error_code = "CAPTURE_CANCELLED"
            operation.error_message = str(error)
            self.operations.update(operation)
            raise ApiError(409, "CAPTURE_CANCELLED", str(error)) from error
        except Exception:
            operation.status = OperationStatus.FAILED
            self.operations.update(operation)
            raise
        self.operations.update(operation)
        return operation

    def cancel_operation(self, operation_id: uuid.UUID):
        operation = self.operations.get(operation_id)
        if operation.status not in InMemoryOperationRepository.ACTIVE:
            raise ApiError(409, "OPERATION_NOT_ACTIVE", "operation is not active")
        operation.cancellation.set()
        operation.status = OperationStatus.CANCELLED
        self.operations.update(operation)
        return operation

    def comparison(self, session_id: uuid.UUID):
        session = self.sessions.get(session_id)
        try:
            return compare_session(session)
        except InvalidSessionStateError as error:
            raise ApiError(409, "SESSION_NOT_READY", str(error)) from error

    def diagnosis(self, session_id: uuid.UUID):
        return diagnose_comparison(self.comparison(session_id))

    def correction(self, session_id: uuid.UUID):
        comparison = self.comparison(session_id)
        return derive_correction_need(diagnose_comparison(comparison), comparison)

    def pigment_candidates(self, session_id: uuid.UUID, context: PaintContext):
        return evaluate_pigment_candidates(
            self.correction(session_id), context, self.knowledge_base
        )

    def create_adjustment(
        self,
        session_id: uuid.UUID,
        context: PaintContext,
        volume_ml,
        components: tuple[AdjustmentComponent, ...],
        operator_reason: str,
        *,
        base_identifier: str | None,
        color_description: str | None,
    ):
        with self._adjustment_lock:
            active = self.adjustments.active_pending()
            if active is not None:
                raise ApiError(
                    409,
                    "PENDING_ADJUSTMENT_EXISTS",
                    "an applied adjustment is still waiting for AFTER",
                    {"adjustment_id": str(active.adjustment_id)},
                )
            session = self.sessions.get(session_id)
            try:
                pending = plan_adjustment(
                    session, context, volume_ml, components, operator_reason,
                    self.knowledge_base, base_identifier=base_identifier,
                    color_description=color_description,
                )
            except ValueError as error:
                raise ApiError(409, "ADJUSTMENT_INVALID_STATE", str(error)) from error
            self.adjustments.save(pending)
            return pending

    def confirm_adjustment_applied(self, adjustment_id: uuid.UUID):
        with self._adjustment_lock:
            adjustment = self.adjustments.get(adjustment_id)
            if not isinstance(adjustment, PendingAdjustment):
                raise ApiError(409, "ADJUSTMENT_ALREADY_COMPLETED", "adjustment is completed")
            try:
                applied = AdjustmentWorkflow(
                    self.instrument, pending_repository=self.pending_repository
                ).confirm_applied(adjustment)
            except ValueError as error:
                raise ApiError(409, "ADJUSTMENT_INVALID_STATE", str(error)) from error
            self.adjustments.save(applied)
            return applied

    def abandon_adjustment(self, adjustment_id: uuid.UUID, observation: str):
        with self._adjustment_lock:
            adjustment = self.adjustments.get(adjustment_id)
            if not isinstance(adjustment, PendingAdjustment):
                raise ApiError(409, "ADJUSTMENT_ALREADY_COMPLETED", "adjustment is completed")
            try:
                abandoned = adjustment.abandon_after_application(observation)
            except ValueError as error:
                raise ApiError(409, "ADJUSTMENT_INVALID_STATE", str(error)) from error
            if self.pending_repository is not None:
                self.pending_repository.save(abandoned)
            self.adjustments.save(abandoned)
            return abandoned

    def update_adjustment_feedback(
        self,
        adjustment_id: uuid.UUID,
        visual_result: VisualResult,
        operator_status: OperatorTrialStatus,
        observations: str | None,
    ):
        with self._adjustment_lock:
            adjustment = self.adjustments.get(adjustment_id)
            if not isinstance(adjustment, CompletedAdjustmentTrial):
                raise ApiError(409, "ADJUSTMENT_NOT_COMPLETED", "adjustment is not completed")
            updated = adjustment.with_operator_feedback(
                visual_result=visual_result,
                operator_status=operator_status,
                observations=observations,
            )
            self.adjustments.save(updated)
            return updated

    def shutdown(self) -> None:
        self.operations.cancel_all()
        self.disconnect()
