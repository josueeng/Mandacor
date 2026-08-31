from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from mandacor.application.measurement_wait import (
    MeasurementSnapshot,
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.domain.measurements import Measurement
from mandacor.domain.sessions import (
    ColorSession,
    SessionInstrumentMismatchError,
)


logger = logging.getLogger(__name__)


class ExistingMeasurementCannotBeSampleError(ValueError):
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
class SampleCaptureRequest:
    base_session: ColorSession
    waiting_session: ColorSession
    snapshot: MeasurementSnapshot


@dataclass(frozen=True, slots=True)
class SampleCaptureResult:
    session: ColorSession
    measurement: Measurement
    elapsed: float
    replaced_existing_sample: bool


class CaptureSampleService:
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

    def prepare_sample_capture(self, session: ColorSession) -> SampleCaptureRequest:
        self._validate_session_instrument(session)
        waiting_session = session.begin_sample_capture()
        snapshot = self._measurement_operations.create_measurement_snapshot()
        logger.info(
            "sample capture prepared",
            extra={
                "session_id": str(session.session_id),
                "snapshot_count": len(snapshot.identities),
                "replacing": session.sample is not None,
            },
        )
        return SampleCaptureRequest(
            base_session=session,
            waiting_session=waiting_session,
            snapshot=snapshot,
        )

    def capture_sample(
        self,
        session: ColorSession,
        request: SampleCaptureRequest,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
    ) -> SampleCaptureResult:
        self._validate_session_instrument(session)
        if session != request.base_session:
            raise ValueError("session changed after sample capture was prepared")
        replaced = session.sample is not None
        logger.info(
            "sample capture started",
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
                "sample capture timed out",
                extra={"session_id": str(session.session_id), "replacing": replaced},
            )
            raise
        except MeasurementWaitCancelledError:
            logger.warning(
                "sample capture cancelled",
                extra={"session_id": str(session.session_id), "replacing": replaced},
            )
            raise
        elapsed = self._monotonic() - started
        if request.snapshot.contains(measurement):
            raise ExistingMeasurementCannotBeSampleError(
                "measurement already existed when sample capture was prepared"
            )
        updated = session.with_sample(measurement)
        logger.info(
            "sample replaced" if replaced else "sample captured",
            extra={
                "session_id": str(session.session_id),
                "measurement_id": measurement.measurement_id,
            },
        )
        return SampleCaptureResult(
            session=updated,
            measurement=measurement,
            elapsed=elapsed,
            replaced_existing_sample=replaced,
        )
