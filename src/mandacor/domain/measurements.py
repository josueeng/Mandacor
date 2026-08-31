from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from numbers import Real
from types import MappingProxyType
from typing import Mapping


class MeasurementError(Exception):
    """Base error for measurement operations and invariants."""


class MeasurementNotFoundError(MeasurementError):
    pass


class IncompleteMeasurementError(MeasurementError):
    pass


class InvalidMeasurementValueError(MeasurementError, ValueError):
    pass


class MeasurementAngle(IntEnum):
    DEG_15 = 15
    DEG_25 = 25
    DEG_45 = 45
    DEG_75 = 75
    DEG_105 = 105


REQUIRED_MEASUREMENT_ANGLES: tuple[MeasurementAngle, ...] = tuple(MeasurementAngle)


def _finite_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidMeasurementValueError(f"{field_name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise InvalidMeasurementValueError(f"{field_name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class LabValue:
    L: float
    a: float
    b: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "L", _finite_float(self.L, field_name="L"))
        object.__setattr__(self, "a", _finite_float(self.a, field_name="a"))
        object.__setattr__(self, "b", _finite_float(self.b, field_name="b"))


@dataclass(frozen=True, slots=True)
class MeasurementReference:
    measurement_id: int
    guid: str | None = None
    name: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class Measurement:
    measurement_id: int
    angles: Mapping[MeasurementAngle, LabValue]
    guid: str | None = None
    timestamp: datetime | None = None
    timestamp_raw: str | None = None
    name: str | None = None
    instrument_serial: str | None = None
    temperature: float | None = None

    def __post_init__(self) -> None:
        normalized: dict[MeasurementAngle, LabValue] = {}
        for angle, value in self.angles.items():
            try:
                normalized_angle = MeasurementAngle(angle)
            except (TypeError, ValueError) as error:
                raise InvalidMeasurementValueError(f"unexpected measurement angle: {angle!r}") from error
            if not isinstance(value, LabValue):
                raise InvalidMeasurementValueError(
                    f"angle {int(normalized_angle)} must contain LabValue"
                )
            normalized[normalized_angle] = value
        required = set(REQUIRED_MEASUREMENT_ANGLES)
        present = set(normalized)
        missing = sorted(int(angle) for angle in required - present)
        if missing:
            raise IncompleteMeasurementError(f"missing required measurement angles: {missing}")
        unexpected = sorted(int(angle) for angle in present - required)
        if unexpected:
            raise InvalidMeasurementValueError(f"unexpected measurement angles: {unexpected}")
        object.__setattr__(self, "angles", MappingProxyType(normalized))
        if self.temperature is not None:
            object.__setattr__(
                self,
                "temperature",
                _finite_float(self.temperature, field_name="temperature"),
            )

