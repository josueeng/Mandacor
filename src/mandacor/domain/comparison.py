from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    InvalidMeasurementValueError,
    LabValue,
    Measurement,
    MeasurementAngle,
    REQUIRED_MEASUREMENT_ANGLES,
)


def _require_finite(value: float, *, field_name: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise InvalidMeasurementValueError(f"{field_name} must be finite")
    return converted


def _validate_lab(lab: LabValue, *, role: str, angle: MeasurementAngle) -> None:
    if not isinstance(lab, LabValue):
        raise InvalidMeasurementValueError(
            f"{role} angle {int(angle)} must contain LabValue"
        )
    _require_finite(lab.L, field_name=f"{role} L* {int(angle)}")
    _require_finite(lab.a, field_name=f"{role} a* {int(angle)}")
    _require_finite(lab.b, field_name=f"{role} b* {int(angle)}")


@dataclass(frozen=True, slots=True)
class AngleComparison:
    angle: MeasurementAngle
    delta_l: float
    delta_a: float
    delta_b: float
    delta_e76: float

    def __post_init__(self) -> None:
        try:
            normalized_angle = MeasurementAngle(self.angle)
        except (TypeError, ValueError) as error:
            raise InvalidMeasurementValueError(
                f"unexpected comparison angle: {self.angle!r}"
            ) from error
        object.__setattr__(self, "angle", normalized_angle)
        for field_name in ("delta_l", "delta_a", "delta_b", "delta_e76"):
            object.__setattr__(
                self,
                field_name,
                _require_finite(getattr(self, field_name), field_name=field_name),
            )
        if self.delta_e76 < 0:
            raise InvalidMeasurementValueError("delta_e76 must be non-negative")


@dataclass(frozen=True, slots=True)
class ColorComparison:
    session_id: uuid.UUID
    target_measurement_id: int
    sample_measurement_id: int
    angles: Mapping[MeasurementAngle, AngleComparison]
    target_guid: str | None = None
    sample_guid: str | None = None

    def __post_init__(self) -> None:
        normalized: dict[MeasurementAngle, AngleComparison] = {}
        for angle in REQUIRED_MEASUREMENT_ANGLES:
            try:
                comparison = self.angles[angle]
            except KeyError as error:
                raise IncompleteMeasurementError(
                    f"comparison missing required angle: {int(angle)}"
                ) from error
            if not isinstance(comparison, AngleComparison):
                raise InvalidMeasurementValueError(
                    f"comparison angle {int(angle)} must contain AngleComparison"
                )
            if comparison.angle is not angle:
                raise InvalidMeasurementValueError(
                    f"comparison key {int(angle)} contains angle {int(comparison.angle)}"
                )
            normalized[angle] = comparison
        if len(self.angles) != len(REQUIRED_MEASUREMENT_ANGLES):
            raise InvalidMeasurementValueError("comparison contains unexpected angles")
        object.__setattr__(self, "angles", MappingProxyType(normalized))


def compare_measurements(
    session_id: uuid.UUID,
    target: Measurement,
    sample: Measurement,
) -> ColorComparison:
    comparisons: dict[MeasurementAngle, AngleComparison] = {}
    for angle in REQUIRED_MEASUREMENT_ANGLES:
        try:
            target_lab = target.angles[angle]
            sample_lab = sample.angles[angle]
        except KeyError as error:
            raise IncompleteMeasurementError(
                f"target or sample missing required angle: {int(angle)}"
            ) from error
        _validate_lab(target_lab, role="target", angle=angle)
        _validate_lab(sample_lab, role="sample", angle=angle)
        delta_l = sample_lab.L - target_lab.L
        delta_a = sample_lab.a - target_lab.a
        delta_b = sample_lab.b - target_lab.b
        delta_e76 = math.sqrt(
            delta_l * delta_l + delta_a * delta_a + delta_b * delta_b
        )
        comparisons[angle] = AngleComparison(
            angle=angle,
            delta_l=delta_l,
            delta_a=delta_a,
            delta_b=delta_b,
            delta_e76=delta_e76,
        )
    return ColorComparison(
        session_id=session_id,
        target_measurement_id=target.measurement_id,
        sample_measurement_id=sample.measurement_id,
        target_guid=target.guid,
        sample_guid=sample.guid,
        angles=comparisons,
    )
