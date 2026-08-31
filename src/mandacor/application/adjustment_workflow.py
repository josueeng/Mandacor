from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol

from mandacor.application.measurement_wait import MeasurementSnapshot
from mandacor.domain.adjustments import (
    AdjustmentError,
    AdjustmentHistory,
    AdjustmentLifecycle,
    CompletedAdjustmentTrial,
    OperatorTrialStatus,
    PendingAdjustment,
    VisualResult,
    complete_adjustment_trial,
)
from mandacor.domain.measurements import Measurement
from mandacor.domain.sessions import ColorSession


class AfterCaptureOperations(Protocol):
    def create_measurement_snapshot(self) -> MeasurementSnapshot: ...

    def wait_for_new_measurement(
        self,
        snapshot: MeasurementSnapshot,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
    ) -> Measurement: ...


class PendingAdjustmentRepository(Protocol):
    def save(self, pending: PendingAdjustment) -> None: ...

    def clear(self, adjustment_id) -> None: ...


@dataclass(frozen=True, slots=True)
class AfterCaptureRequest:
    pending: PendingAdjustment
    snapshot: MeasurementSnapshot


@dataclass(frozen=True, slots=True)
class AdjustmentCompletionResult:
    session: ColorSession
    history: AdjustmentHistory
    trial: CompletedAdjustmentTrial
    measurement: Measurement
    elapsed: float


def _same_measurement(left: Measurement | None, right: Measurement) -> bool:
    if left is None or left.measurement_id != right.measurement_id:
        return False
    if left.guid is not None and right.guid is not None:
        return left.guid == right.guid
    return True


class AdjustmentWorkflow:
    def __init__(
        self,
        measurement_operations: AfterCaptureOperations,
        *,
        pending_repository: PendingAdjustmentRepository | None = None,
        monotonic=time.monotonic,
    ) -> None:
        self._measurement_operations = measurement_operations
        self._pending_repository = pending_repository
        self._monotonic = monotonic

    def confirm_applied(self, planned: PendingAdjustment) -> PendingAdjustment:
        applied = planned.confirm_applied()
        if self._pending_repository is not None:
            self._pending_repository.save(applied)
        return applied

    def prepare_after_capture(self, pending: PendingAdjustment) -> AfterCaptureRequest:
        if pending.lifecycle is not AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER:
            raise AdjustmentError("only an applied adjustment can capture AFTER")
        snapshot = self._measurement_operations.create_measurement_snapshot()
        return AfterCaptureRequest(pending, snapshot)

    def retry_after_capture(self, pending: PendingAdjustment) -> AfterCaptureRequest:
        return self.prepare_after_capture(pending)

    def capture_after(
        self,
        session: ColorSession,
        history: AdjustmentHistory,
        request: AfterCaptureRequest,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
        visual_result: VisualResult = VisualResult.UNKNOWN,
        operator_status: OperatorTrialStatus = OperatorTrialStatus.UNKNOWN,
        observations: str | None = None,
    ) -> AdjustmentCompletionResult:
        pending = request.pending
        if any(item.adjustment_id == pending.adjustment_id for item in history.trials):
            raise AdjustmentError("adjustment is already completed")
        if session.session_id != pending.session_id:
            raise AdjustmentError("session changed after adjustment was planned")
        if not _same_measurement(session.target, pending.target):
            raise AdjustmentError("target changed after adjustment was planned")
        if not _same_measurement(session.sample, pending.before):
            raise AdjustmentError("current sample changed after adjustment was planned")
        started = self._monotonic()
        after = self._measurement_operations.wait_for_new_measurement(
            request.snapshot,
            timeout=timeout,
            poll_interval=poll_interval,
            cancellation=cancellation,
        )
        if request.snapshot.contains(after):
            raise AdjustmentError("AFTER measurement already existed in the snapshot")
        trial = complete_adjustment_trial(
            pending,
            after,
            visual_result=visual_result,
            operator_status=operator_status,
            observations=observations,
        )
        updated_session = session.with_sample(after)
        updated_history = history.append(trial)
        return AdjustmentCompletionResult(
            updated_session,
            updated_history,
            trial,
            after,
            self._monotonic() - started,
        )

    def acknowledge_completed(self, adjustment_id) -> None:
        """Clear recovery state only after the completed trial is durably exported."""
        if self._pending_repository is not None:
            self._pending_repository.clear(adjustment_id)
