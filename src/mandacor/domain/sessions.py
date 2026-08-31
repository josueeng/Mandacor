from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from mandacor.domain.measurements import Measurement


class SessionInstrumentMismatchError(ValueError):
    pass


class InvalidSessionStateError(ValueError):
    pass


class SessionState(str, Enum):
    WAITING_FOR_TARGET = "waiting_for_target"
    TARGET_CAPTURED = "target_captured"
    WAITING_FOR_SAMPLE = "waiting_for_sample"
    READY_FOR_COMPARISON = "ready_for_comparison"


@dataclass(frozen=True, slots=True)
class ColorSession:
    session_id: uuid.UUID
    created_at: datetime
    instrument_serial: str | None
    target: Measurement | None = None
    sample: Measurement | None = None
    state: SessionState = SessionState.WAITING_FOR_TARGET

    def __post_init__(self) -> None:
        coherent = {
            SessionState.WAITING_FOR_TARGET: self.target is None and self.sample is None,
            SessionState.TARGET_CAPTURED: self.target is not None and self.sample is None,
            SessionState.WAITING_FOR_SAMPLE: self.target is not None,
            SessionState.READY_FOR_COMPARISON: (
                self.target is not None and self.sample is not None
            ),
        }
        if not coherent[self.state]:
            raise ValueError("session state is inconsistent with target")
        for role, measurement in (("target", self.target), ("sample", self.sample)):
            if (
                measurement is not None
                and self.instrument_serial is not None
                and measurement.instrument_serial is not None
                and measurement.instrument_serial != self.instrument_serial
            ):
                raise SessionInstrumentMismatchError(
                    f"{role} measurement belongs to another instrument"
                )

    @classmethod
    def create(
        cls,
        instrument_serial: str | None,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> "ColorSession":
        return cls(
            session_id=uuid_factory(),
            created_at=now(),
            instrument_serial=instrument_serial,
        )

    def with_target(self, measurement: Measurement) -> "ColorSession":
        if (
            self.instrument_serial is not None
            and measurement.instrument_serial is not None
            and measurement.instrument_serial != self.instrument_serial
        ):
            raise SessionInstrumentMismatchError(
                "target measurement belongs to another instrument"
            )
        return replace(
            self,
            target=measurement,
            sample=None,
            state=SessionState.TARGET_CAPTURED,
        )

    def replace_target(self, measurement: Measurement) -> "ColorSession":
        """Replace the target while preserving an existing sample."""
        if (
            self.instrument_serial is not None
            and measurement.instrument_serial is not None
            and measurement.instrument_serial != self.instrument_serial
        ):
            raise SessionInstrumentMismatchError(
                "target measurement belongs to another instrument"
            )
        if self.sample is not None:
            same_id = measurement.measurement_id == self.sample.measurement_id
            same_guid = (
                measurement.guid == self.sample.guid
                if measurement.guid is not None and self.sample.guid is not None
                else True
            )
            if same_id and same_guid:
                raise InvalidSessionStateError(
                    "sample measurement cannot also be the target"
                )
        return replace(
            self,
            target=measurement,
            state=(
                SessionState.READY_FOR_COMPARISON
                if self.sample is not None
                else SessionState.TARGET_CAPTURED
            ),
        )

    def begin_sample_capture(self) -> "ColorSession":
        if self.target is None:
            raise InvalidSessionStateError(
                "target is required before sample capture"
            )
        return replace(self, state=SessionState.WAITING_FOR_SAMPLE)

    def with_sample(self, measurement: Measurement) -> "ColorSession":
        if self.target is None:
            raise InvalidSessionStateError(
                "target is required before assigning sample"
            )
        if (
            self.instrument_serial is not None
            and measurement.instrument_serial is not None
            and measurement.instrument_serial != self.instrument_serial
        ):
            raise SessionInstrumentMismatchError(
                "sample measurement belongs to another instrument"
            )
        same_id = measurement.measurement_id == self.target.measurement_id
        same_guid = (
            measurement.guid == self.target.guid
            if measurement.guid is not None and self.target.guid is not None
            else True
        )
        if same_id and same_guid:
            raise InvalidSessionStateError(
                "target measurement cannot also be the sample"
            )
        return replace(
            self,
            sample=measurement,
            state=SessionState.READY_FOR_COMPARISON,
        )
