from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from mandacor.application.measurement_wait import (
    MeasurementSnapshot,
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.domain.measurements import Measurement
from mandacor.domain.sessions import ColorSession, SessionInstrumentMismatchError


logger = logging.getLogger(__name__)


class TargetCaptureError(Exception):
    pass


class ExistingMeasurementCannotBeTargetError(TargetCaptureError):
    pass


class MeasurementWaitOperations(Protocol):
    def create_measurement_snapshot(self) -> MeasurementSnapshot: ...

    def wait_for_new_measurement(
        self,
        snapshot: MeasurementSnapshot,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
    ) -> Measurement: ...


@dataclass(frozen=True, slots=True)
class TargetCaptureRequest:
    session_id: uuid.UUID
    instrument_serial: str | None
    snapshot: MeasurementSnapshot


@dataclass(frozen=True, slots=True)
class TargetCaptureResult:
    session: ColorSession
    measurement: Measurement
    elapsed: float
    replaced_existing_target: bool


class CaptureTargetService:
    def __init__(
        self,
        measurement_operations: MeasurementWaitOperations,
        *,
        instrument_serial: str | None,
        monotonic=time.monotonic,
    ) -> None:
        self._measurement_operations = measurement_operations
        self._instrument_serial = instrument_serial
        self._monotonic = monotonic

    def _validate_session_instrument(self, session: ColorSession) -> None:
        if session.instrument_serial != self._instrument_serial:
            raise SessionInstrumentMismatchError(
                "session belongs to another instrument"
            )

    def prepare_target_capture(self, session: ColorSession) -> TargetCaptureRequest:
        self._validate_session_instrument(session)
        snapshot = self._measurement_operations.create_measurement_snapshot()
        logger.info(
            "target capture prepared",
            extra={
                "session_id": str(session.session_id),
                "snapshot_count": len(snapshot.identities),
            },
        )
        return TargetCaptureRequest(
            session_id=session.session_id,
            instrument_serial=session.instrument_serial,
            snapshot=snapshot,
        )

    def capture_target(
        self,
        session: ColorSession,
        request: TargetCaptureRequest,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
    ) -> TargetCaptureResult:
        self._validate_session_instrument(session)
        if request.session_id != session.session_id:
            raise ValueError("target capture request belongs to another session")
        if request.instrument_serial != session.instrument_serial:
            raise SessionInstrumentMismatchError(
                "target capture request belongs to another instrument"
            )
        replaced = session.target is not None
        logger.info(
            "target capture started",
            extra={"session_id": str(session.session_id), "replacing": replaced},
        )
        started = self._monotonic()
        try:
            measurement = self._measurement_operations.wait_for_new_measurement(
                request.snapshot,
                timeout=timeout,
                poll_interval=poll_interval,
                cancellation=cancellation,
            )
        except NewMeasurementTimeoutError:
            logger.warning(
                "target capture timed out",
                extra={"session_id": str(session.session_id), "replacing": replaced},
            )
            raise
        except MeasurementWaitCancelledError:
            logger.warning(
                "target capture cancelled",
                extra={"session_id": str(session.session_id), "replacing": replaced},
            )
            raise
        elapsed = self._monotonic() - started
        if request.snapshot.contains(measurement):
            raise ExistingMeasurementCannotBeTargetError(
                "measurement already existed when target capture was prepared"
            )
        updated = session.with_target(measurement)
        logger.info(
            "target replaced" if replaced else "target captured",
            extra={
                "session_id": str(session.session_id),
                "measurement_id": measurement.measurement_id,
            },
        )
        return TargetCaptureResult(
            session=updated,
            measurement=measurement,
            elapsed=elapsed,
            replaced_existing_target=replaced,
        )
