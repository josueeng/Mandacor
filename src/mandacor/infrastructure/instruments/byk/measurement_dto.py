from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RawBykMeasurementReference:
    measurement_id: int
    guid: str | None
    name: str | None


@dataclass(frozen=True, slots=True)
class RawBykLabValue:
    L: str | None = None
    a: str | None = None
    b: str | None = None


@dataclass(frozen=True, slots=True)
class RawBykMeasurement:
    measurement_id: int
    guid: str | None
    timestamp: str | None
    name: str | None
    instrument_serial: str | None
    temperature: str | None
    angles: Mapping[int, RawBykLabValue]

