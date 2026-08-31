from __future__ import annotations

import math
import uuid
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mandacor.application.comparison_service import compare_session
from mandacor.domain.comparison import (
    AngleComparison,
    ColorComparison,
    compare_measurements,
)
from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    InvalidMeasurementValueError,
    LabValue,
    Measurement,
    MeasurementAngle,
)
from mandacor.domain.sessions import ColorSession, InvalidSessionStateError, SessionState


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")


def _measurement(
    measurement_id: int,
    lab: LabValue | None = None,
    *,
    per_angle: dict[MeasurementAngle, LabValue] | None = None,
) -> Measurement:
    values = per_angle or {
        angle: lab or LabValue(float(angle), -4.0, -5.0)
        for angle in MeasurementAngle
    }
    return Measurement(
        measurement_id,
        values,
        guid=f"guid-{measurement_id}",
        instrument_serial="instrument-A",
    )


def _ready_session(target: Measurement, sample: Measurement) -> ColorSession:
    return ColorSession.create(
        "instrument-A", uuid_factory=lambda: SESSION_ID
    ).with_target(target).with_sample(sample)


def test_compare_identical_measurements_returns_zero_at_all_angles():
    target = _measurement(12, LabValue(50.0, 2.0, -3.0))
    sample = _measurement(13, LabValue(50.0, 2.0, -3.0))
    result = compare_measurements(SESSION_ID, target, sample)
    assert tuple(result.angles) == tuple(MeasurementAngle)
    assert len(result.angles) == 5
    for comparison in result.angles.values():
        assert comparison.delta_l == 0.0
        assert comparison.delta_a == 0.0
        assert comparison.delta_b == 0.0
        assert comparison.delta_e76 == 0.0


def test_comparison_uses_sample_minus_target_with_explicit_positive_signs():
    target = _measurement(12, LabValue(50.0, 1.0, 2.0))
    sample = _measurement(13, LabValue(55.0, 3.0, 5.0))
    angle = compare_measurements(SESSION_ID, target, sample).angles[MeasurementAngle.DEG_15]
    assert angle.delta_l == 5.0
    assert angle.delta_a == 2.0
    assert angle.delta_b == 3.0


@pytest.mark.parametrize(
    ("target_lab", "sample_lab", "field", "expected"),
    [
        (LabValue(50, 0, 0), LabValue(45, 0, 0), "delta_l", -5.0),
        (LabValue(0, 1, 0), LabValue(0, -1, 0), "delta_a", -2.0),
        (LabValue(0, 0, 2), LabValue(0, 0, -1), "delta_b", -3.0),
        (LabValue(0, -4, 0), LabValue(0, -2, 0), "delta_a", 2.0),
        (LabValue(0, 0, -5), LabValue(0, 0, -2), "delta_b", 3.0),
    ],
)
def test_signs_and_negative_axis_values_are_subtracted_relatively(
    target_lab, sample_lab, field, expected
):
    result = compare_measurements(
        SESSION_ID, _measurement(12, target_lab), _measurement(13, sample_lab)
    )
    assert getattr(result.angles[MeasurementAngle.DEG_15], field) == expected


@pytest.mark.parametrize(
    ("sample_lab", "expected"),
    [
        (LabValue(3, 4, 0), 5.0),
        (LabValue(1, 2, 2), 3.0),
    ],
)
def test_delta_e76_known_vectors(sample_lab, expected):
    result = compare_measurements(
        SESSION_ID,
        _measurement(12, LabValue(0, 0, 0)),
        _measurement(13, sample_lab),
    )
    for angle in result.angles.values():
        assert angle.delta_e76 == pytest.approx(expected)
        assert angle.delta_e76 >= 0


def test_multi_angle_values_are_not_cross_compared_and_order_is_canonical():
    target_values = {
        angle: LabValue(index * 10.0, index * -2.0, index * 3.0)
        for index, angle in enumerate(reversed(tuple(MeasurementAngle)), start=1)
    }
    expected = {
        angle: LabValue(index + 0.1, index + 0.2, index + 0.3)
        for index, angle in enumerate(MeasurementAngle, start=1)
    }
    sample_values = {
        angle: LabValue(
            target_values[angle].L + delta.L,
            target_values[angle].a + delta.a,
            target_values[angle].b + delta.b,
        )
        for angle, delta in expected.items()
    }
    result = compare_measurements(
        SESSION_ID,
        _measurement(12, per_angle=target_values),
        _measurement(13, per_angle=sample_values),
    )
    assert tuple(result.angles) == tuple(MeasurementAngle)
    for angle, delta in expected.items():
        actual = result.angles[angle]
        assert actual.angle is angle
        assert actual.delta_l == pytest.approx(delta.L)
        assert actual.delta_a == pytest.approx(delta.a)
        assert actual.delta_b == pytest.approx(delta.b)


def test_precision_is_preserved_without_domain_rounding():
    target = _measurement(12, LabValue(77.1218414, 0.123456789, -0.987654321))
    sample = _measurement(13, LabValue(77.2218414, 0.223456781, -0.887654329))
    result = compare_measurements(SESSION_ID, target, sample)
    angle = result.angles[MeasurementAngle.DEG_15]
    assert angle.delta_l == pytest.approx(0.1)
    assert angle.delta_a == pytest.approx(0.099999992)
    assert angle.delta_b == pytest.approx(0.099999992)
    assert angle.delta_l != round(angle.delta_l, 2)


def test_nontrivial_decimal_delta_e_uses_independent_expected_formula():
    target_lab = LabValue(41.234567, -3.210987, 6.543219)
    sample_lab = LabValue(43.876543, -1.109876, 2.345678)
    dl = sample_lab.L - target_lab.L
    da = sample_lab.a - target_lab.a
    db = sample_lab.b - target_lab.b
    expected = math.sqrt(dl * dl + da * da + db * db)
    actual = compare_measurements(
        SESSION_ID, _measurement(12, target_lab), _measurement(13, sample_lab)
    ).angles[MeasurementAngle.DEG_45]
    assert actual.delta_e76 == pytest.approx(expected)


def test_comparison_preserves_session_measurement_ids_and_guids():
    result = compare_measurements(
        SESSION_ID, _measurement(12), _measurement(13)
    )
    assert result.session_id == SESSION_ID
    assert result.target_measurement_id == 12
    assert result.target_guid == "guid-12"
    assert result.sample_measurement_id == 13
    assert result.sample_guid == "guid-13"


def test_models_results_and_inputs_are_immutable_and_not_mutated():
    target = _measurement(12)
    sample = _measurement(13, LabValue(16, -2, -1))
    target_before = tuple(target.angles.items())
    sample_before = tuple(sample.angles.items())
    session = _ready_session(target, sample)
    comparison = compare_session(session)
    assert tuple(target.angles.items()) == target_before
    assert tuple(sample.angles.items()) == sample_before
    assert session.state is SessionState.READY_FOR_COMPARISON
    assert session.target is target and session.sample is sample
    with pytest.raises(FrozenInstanceError):
        comparison.sample_measurement_id = 99
    with pytest.raises(FrozenInstanceError):
        comparison.angles[MeasurementAngle.DEG_15].delta_l = 99
    with pytest.raises(TypeError):
        comparison.angles[MeasurementAngle.DEG_15] = comparison.angles[
            MeasurementAngle.DEG_25
        ]


def test_comparison_defensively_rejects_missing_angle():
    target = _measurement(12)
    sample = _measurement(13)
    incomplete = dict(sample.angles)
    del incomplete[MeasurementAngle.DEG_105]
    object.__setattr__(sample, "angles", MappingProxyType(incomplete))
    with pytest.raises(IncompleteMeasurementError):
        compare_measurements(SESSION_ID, target, sample)


def test_comparison_defensively_rejects_non_finite_result():
    target = _measurement(12)
    sample = _measurement(13)
    object.__setattr__(sample.angles[MeasurementAngle.DEG_15], "L", float("nan"))
    with pytest.raises(InvalidMeasurementValueError):
        compare_measurements(SESSION_ID, target, sample)


def test_compare_session_requires_target():
    with pytest.raises(InvalidSessionStateError, match="ready"):
        compare_session(ColorSession.create("instrument-A"))


def test_compare_session_requires_sample():
    session = ColorSession.create("instrument-A").with_target(_measurement(12))
    with pytest.raises(InvalidSessionStateError, match="ready"):
        compare_session(session)


def test_compare_session_requires_ready_state_even_when_both_roles_exist():
    session = _ready_session(_measurement(12), _measurement(13)).begin_sample_capture()
    assert session.target is not None and session.sample is not None
    assert session.state is SessionState.WAITING_FOR_SAMPLE
    with pytest.raises(InvalidSessionStateError, match="ready"):
        compare_session(session)


def test_compare_session_ready_state_succeeds_without_mutating_session():
    session = _ready_session(_measurement(12), _measurement(13))
    result = compare_session(session)
    assert isinstance(result, ColorComparison)
    assert all(isinstance(item, AngleComparison) for item in result.angles.values())
    assert result.session_id == session.session_id
    assert session.state is SessionState.READY_FOR_COMPARISON
