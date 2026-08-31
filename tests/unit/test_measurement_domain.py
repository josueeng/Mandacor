from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    InvalidMeasurementValueError,
    LabValue,
    Measurement,
    MeasurementAngle,
)


def _valid_angles():
    return {angle: LabValue(float(angle), 1.0, -1.0) for angle in MeasurementAngle}


def test_valid_measurement_has_exactly_five_immutable_angles():
    measurement = Measurement(1, _valid_angles())
    assert set(measurement.angles) == set(MeasurementAngle)
    assert len([value for lab in measurement.angles.values() for value in (lab.L, lab.a, lab.b)]) == 15
    with pytest.raises(TypeError):
        measurement.angles[MeasurementAngle.DEG_15] = LabValue(0, 0, 0)
    with pytest.raises(FrozenInstanceError):
        measurement.name = "changed"


def test_domain_rejects_missing_angle():
    angles = _valid_angles()
    del angles[MeasurementAngle.DEG_105]
    with pytest.raises(IncompleteMeasurementError):
        Measurement(1, angles)


@pytest.mark.parametrize("value", [None, "1.2", float("nan"), float("inf"), -float("inf"), True])
def test_lab_value_rejects_missing_non_numeric_or_non_finite(value):
    with pytest.raises(InvalidMeasurementValueError):
        LabValue(value, 0.0, 0.0)

