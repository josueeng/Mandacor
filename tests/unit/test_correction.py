from __future__ import annotations

import math
import uuid
from dataclasses import FrozenInstanceError

import pytest

from mandacor.domain.comparison import AngleComparison, ColorComparison
from mandacor.domain.correction import (
    AngleGroup,
    ColorCorrectionNeed,
    LightnessAction,
    RedGreenAction,
    Uniformity,
    YellowBlueAction,
    derive_correction_need,
)
from mandacor.domain.diagnosis import DominantAxis, diagnose_comparison
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.measurements import LabValue, Measurement
from mandacor.domain.sessions import ColorSession
from mandacor.application.comparison_service import compare_session


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")
REAL_DELTAS = {
    MeasurementAngle.DEG_15: (-2.667785600000002, 0.11980533589999999, -0.07293820360000002),
    MeasurementAngle.DEG_25: (-1.5255966, 0.18647313110000002, 0.297808647),
    MeasurementAngle.DEG_45: (-0.25867840000000086, 0.19317865420000002, 0.4388928418),
    MeasurementAngle.DEG_75: (0.051396300000000394, 0.14901161227, 0.3870666025),
    MeasurementAngle.DEG_105: (0.11994270000000107, 0.1265108589, 0.3580033778),
}


def _comparison(
    deltas: dict[MeasurementAngle, tuple[float, float, float]] | None = None,
) -> ColorComparison:
    values = deltas or {angle: (0.0, 0.0, 0.0) for angle in MeasurementAngle}
    return ColorComparison(
        session_id=SESSION_ID,
        target_measurement_id=12,
        sample_measurement_id=13,
        target_guid="target-guid",
        sample_guid="sample-guid",
        angles={
            angle: AngleComparison(angle, dl, da, db, math.sqrt(dl**2 + da**2 + db**2))
            for angle, (dl, da, db) in values.items()
        },
    )


def _uniform(dl: float, da: float, db: float) -> ColorComparison:
    return _comparison({angle: (dl, da, db) for angle in MeasurementAngle})


def _derive(comparison: ColorComparison) -> ColorCorrectionNeed:
    return derive_correction_need(diagnose_comparison(comparison), comparison)


@pytest.mark.parametrize(
    ("deltas", "field", "expected"),
    [
        ((-1, 0, 0), "lightness_action", LightnessAction.LIGHTEN),
        ((1, 0, 0), "lightness_action", LightnessAction.DARKEN),
        ((0, 1, 0), "red_green_action", RedGreenAction.MOVE_GREENER),
        ((0, -1, 0), "red_green_action", RedGreenAction.MOVE_REDDER),
        ((0, 0, 1), "yellow_blue_action", YellowBlueAction.MOVE_BLUER),
        ((0, 0, -1), "yellow_blue_action", YellowBlueAction.MOVE_YELLOWER),
        ((0, 0, 0), "lightness_action", LightnessAction.NONE),
        ((0, 0, 0), "red_green_action", RedGreenAction.NONE),
        ((0, 0, 0), "yellow_blue_action", YellowBlueAction.NONE),
    ],
)
def test_observed_direction_is_inverted_into_correction_action(deltas, field, expected):
    need = _derive(_uniform(*deltas)).by_angle[MeasurementAngle.DEG_15]
    assert getattr(need, field) is expected


def test_correction_vector_is_exact_negative_of_comparison_delta():
    comparison = _uniform(-3, 2, -1)
    need = _derive(comparison).by_angle[MeasurementAngle.DEG_15]
    assert (need.correction_delta_l, need.correction_delta_a, need.correction_delta_b) == (3, -2, 1)


def test_front_uniform_action_is_preserved_and_conflict_becomes_mixed():
    values = {angle: (-1, 0, 0) for angle in MeasurementAngle}
    assert _derive(_comparison(values)).front.lightness_action is LightnessAction.LIGHTEN
    values[MeasurementAngle.DEG_25] = (1, 0, 0)
    assert _derive(_comparison(values)).front.lightness_action is LightnessAction.MIXED


def test_flop_uniform_action_is_preserved_and_conflict_becomes_mixed():
    values = {angle: (0, 0, 1) for angle in MeasurementAngle}
    assert _derive(_comparison(values)).flop.yellow_blue_action is YellowBlueAction.MOVE_BLUER
    values[MeasurementAngle.DEG_105] = (0, 0, -1)
    assert _derive(_comparison(values)).flop.yellow_blue_action is YellowBlueAction.MIXED


def test_global_uniformity_requires_all_five_angles():
    uniform = _derive(_uniform(0, 1, 0))
    assert uniform.global_actions.red_green_action is RedGreenAction.MOVE_GREENER
    assert uniform.global_uniformity.red_green is Uniformity.UNIFORM
    assert uniform.is_uniform_across_angles(DominantAxis.A)
    values = {angle: (0, 1, 0) for angle in MeasurementAngle}
    values[MeasurementAngle.DEG_105] = (0, -1, 0)
    mixed = _derive(_comparison(values))
    assert mixed.global_actions.red_green_action is RedGreenAction.MIXED
    assert mixed.global_uniformity.red_green is Uniformity.MIXED
    assert not mixed.is_uniform_across_angles(DominantAxis.A)


def test_each_multiangle_flag_is_descriptive_and_axis_specific():
    values = {angle: (-1, 1, 1) for angle in MeasurementAngle}
    values[MeasurementAngle.DEG_105] = (1, -1, -1)
    flags = _derive(_comparison(values)).multiangle_flags
    assert flags.lightness_action_varies_by_angle
    assert flags.red_green_action_varies_by_angle
    assert flags.yellow_blue_action_varies_by_angle


def test_five_angles_and_operational_groups_are_preserved():
    result = _derive(_comparison(REAL_DELTAS))
    assert tuple(result.by_angle) == tuple(MeasurementAngle)
    assert result.front.angles == (MeasurementAngle.DEG_15, MeasurementAngle.DEG_25)
    assert result.mid.angle is MeasurementAngle.DEG_45
    assert result.flop.angles == (MeasurementAngle.DEG_75, MeasurementAngle.DEG_105)


def test_real_gate6_case_has_expected_needs_regions_flags_and_primary_issue():
    result = _derive(_comparison(REAL_DELTAS))
    expected_l = [LightnessAction.LIGHTEN] * 3 + [LightnessAction.DARKEN] * 2
    expected_a = [RedGreenAction.MOVE_GREENER] * 5
    expected_b = [YellowBlueAction.MOVE_YELLOWER] + [YellowBlueAction.MOVE_BLUER] * 4
    assert [item.lightness_action for item in result.by_angle.values()] == expected_l
    assert [item.red_green_action for item in result.by_angle.values()] == expected_a
    assert [item.yellow_blue_action for item in result.by_angle.values()] == expected_b
    assert result.front.lightness_action is LightnessAction.LIGHTEN
    assert result.front.yellow_blue_action is YellowBlueAction.MIXED
    assert result.mid.lightness_action is LightnessAction.LIGHTEN
    assert result.mid.yellow_blue_action is YellowBlueAction.MOVE_BLUER
    assert result.flop.lightness_action is LightnessAction.DARKEN
    assert result.flop.yellow_blue_action is YellowBlueAction.MOVE_BLUER
    assert result.global_actions.lightness_action is LightnessAction.MIXED
    assert result.global_actions.red_green_action is RedGreenAction.MOVE_GREENER
    assert result.global_actions.yellow_blue_action is YellowBlueAction.MIXED
    assert result.multiangle_flags.multiangle_lightness_mismatch
    assert not result.multiangle_flags.red_green_action_varies_by_angle
    assert result.multiangle_flags.yellow_blue_action_varies_by_angle
    assert result.worst_angle is MeasurementAngle.DEG_15
    assert result.primary_issue.angle is MeasurementAngle.DEG_15
    assert result.primary_issue.group is AngleGroup.FRONT
    assert result.primary_issue.axis is DominantAxis.L
    assert result.primary_issue.action is LightnessAction.LIGHTEN


def test_absolute_negative_lab_axes_are_irrelevant_because_input_is_diagnosis_and_delta():
    result = _derive(_uniform(0, 2, 0))
    assert result.by_angle[MeasurementAngle.DEG_15].red_green_action is RedGreenAction.MOVE_GREENER


def test_derive_is_deterministic_immutable_and_does_not_mutate_inputs():
    comparison = _comparison(REAL_DELTAS)
    diagnosis = diagnose_comparison(comparison)
    comparison_before = tuple(comparison.angles.items())
    diagnosis_before = tuple(diagnosis.angle_diagnoses.items())
    first = derive_correction_need(diagnosis, comparison)
    second = derive_correction_need(diagnosis, comparison)
    assert first == second
    assert tuple(comparison.angles.items()) == comparison_before
    assert tuple(diagnosis.angle_diagnoses.items()) == diagnosis_before
    with pytest.raises(FrozenInstanceError):
        first.worst_angle = MeasurementAngle.DEG_105
    with pytest.raises(TypeError):
        first.by_angle[MeasurementAngle.DEG_15] = first.by_angle[MeasurementAngle.DEG_25]


def test_full_flow_does_not_mutate_session_or_measurements():
    target = Measurement(12, {angle: LabValue(50, -4, -5) for angle in MeasurementAngle})
    sample = Measurement(13, {angle: LabValue(49, -2, -6) for angle in MeasurementAngle})
    session = ColorSession.create("instrument-A", uuid_factory=lambda: SESSION_ID).with_target(target).with_sample(sample)
    target_before = tuple(target.angles.items())
    sample_before = tuple(sample.angles.items())
    comparison = compare_session(session)
    derive_correction_need(diagnose_comparison(comparison), comparison)
    assert session.target is target and session.sample is sample
    assert tuple(target.angles.items()) == target_before
    assert tuple(sample.angles.items()) == sample_before


def test_mismatched_diagnosis_and_comparison_are_rejected():
    comparison = _comparison(REAL_DELTAS)
    other = ColorComparison(
        session_id=uuid.uuid4(),
        target_measurement_id=12,
        sample_measurement_id=13,
        angles=comparison.angles,
    )
    with pytest.raises(ValueError, match="different measurements"):
        derive_correction_need(diagnose_comparison(comparison), other)


def test_domain_has_no_byk_pigment_grams_or_ml_dependency():
    source = __import__("inspect").getsource(__import__("mandacor.domain.correction", fromlist=["*"]))
    lowered = source.lower()
    assert "infrastructure" not in lowered
    assert "byk" not in lowered
    assert "pigment" not in lowered
    assert "grams" not in lowered
    assert "machine learning" not in lowered
