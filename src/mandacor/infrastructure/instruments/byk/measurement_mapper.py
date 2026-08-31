from __future__ import annotations

import math
from datetime import datetime

from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    InvalidMeasurementValueError,
    LabValue,
    Measurement,
    MeasurementAngle,
    MeasurementReference,
    REQUIRED_MEASUREMENT_ANGLES,
)
from mandacor.infrastructure.instruments.byk.measurement_dto import (
    RawBykMeasurement,
    RawBykMeasurementReference,
)


def _parse_finite(value: str | None, *, field_name: str) -> float:
    if value is None:
        raise IncompleteMeasurementError(f"missing {field_name}")
    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise InvalidMeasurementValueError(f"invalid {field_name}: {value!r}") from error
    if not math.isfinite(converted):
        raise InvalidMeasurementValueError(f"non-finite {field_name}: {value!r}")
    return converted


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise InvalidMeasurementValueError(f"invalid measurement timestamp: {value!r}") from error


def map_measurement_reference(raw: RawBykMeasurementReference) -> MeasurementReference:
    return MeasurementReference(
        measurement_id=raw.measurement_id,
        guid=raw.guid,
        name=raw.name,
        timestamp=None,
    )


def map_measurement(raw: RawBykMeasurement) -> Measurement:
    missing_angles = [
        int(angle) for angle in REQUIRED_MEASUREMENT_ANGLES if int(angle) not in raw.angles
    ]
    if missing_angles:
        raise IncompleteMeasurementError(f"missing required measurement angles: {missing_angles}")
    angles: dict[MeasurementAngle, LabValue] = {}
    for angle, raw_lab in raw.angles.items():
        try:
            domain_angle = MeasurementAngle(angle)
        except ValueError as error:
            raise InvalidMeasurementValueError(f"unexpected measurement angle: {angle}") from error
        angles[domain_angle] = LabValue(
            L=_parse_finite(raw_lab.L, field_name=f"L* {angle}"),
            a=_parse_finite(raw_lab.a, field_name=f"a* {angle}"),
            b=_parse_finite(raw_lab.b, field_name=f"b* {angle}"),
        )
    temperature = (
        None
        if raw.temperature is None
        else _parse_finite(raw.temperature, field_name="DeviceTemperature")
    )
    return Measurement(
        measurement_id=raw.measurement_id,
        guid=raw.guid,
        timestamp=_parse_timestamp(raw.timestamp),
        timestamp_raw=raw.timestamp,
        name=raw.name,
        instrument_serial=raw.instrument_serial,
        temperature=temperature,
        angles=angles,
    )

