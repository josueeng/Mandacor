from __future__ import annotations

import math
import uuid
from dataclasses import FrozenInstanceError

import pytest

from mandacor.domain.comparison import (
    AngleComparison,
    ColorComparison,
    compare_measurements,
)
from mandacor.domain.diagnosis import (
    AxisSignPattern,
    ColorDiagnosis,
    DominantAxis,
    LightnessDirection,
    LightnessTrend,
    RedGreenDirection,
    YellowBlueDirection,
    diagnose_comparison,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")
REAL_DELTAS = {
    MeasurementAngle.DEG_15: (-2.667785600000002, 0.11980533589999999, -0.07293820360000002, 2.6714702520563236),
    MeasurementAngle.DEG_25: (-1.5255966, 0.18647313110000002, 0.297808647, 1.5655373533652173),
    MeasurementAngle.DEG_45: (-0.25867840000000086, 0.19317865420000002, 0.4388928418, 0.5448480830913911),
    MeasurementAngle.DEG_75: (0.051396300000000394, 0.14901161227, 0.3870666025, 0.4179313281101189),
    MeasurementAngle.DEG_105: (0.11994270000000107, 0.1265108589, 0.3580033778, 0.3981930024738199),
}


def _comparison(
    deltas: dict[MeasurementAngle, tuple[float, float, float, float]] | None = None,
) -> ColorComparison:
    values = deltas or {
        angle: (0.0, 0.0, 0.0, 0.0) for angle in MeasurementAngle
    }
    return ColorComparison(
        session_id=SESSION_ID,
        target_measurement_id=12,
        sample_measurement_id=13,
        target_guid="target-guid",
        sample_guid="sample-guid",
        angles={
            angle: AngleComparison(angle, delta_l, delta_a, delta_b, delta_e)
            for angle, (delta_l, delta_a, delta_b, delta_e) in values.items()
        },
    )


def _uniform(delta_l: float, delta_a: float, delta_b: float) -> ColorComparison:
    delta_e = math.sqrt(delta_l**2 + delta_a**2 + delta_b**2)
    return _comparison(
        {
            angle: (delta_l, delta_a, delta_b, delta_e)
            for angle in MeasurementAngle
        }
    )


@pytest.mark.parametrize(
    ("comparison", "field", "expected"),
    [
        (_uniform(-1, 0, 0), "lightness_direction", LightnessDirection.DARKER),
        (_uniform(1, 0, 0), "lightness_direction", LightnessDirection.LIGHTER),
        (_uniform(0, 1, 0), "red_green_direction", RedGreenDirection.REDDER),
        (_uniform(0, -1, 0), "red_green_direction", RedGreenDirection.GREENER),
        (_uniform(0, 0, 1), "yellow_blue_direction", YellowBlueDirection.YELLOWER),
        (_uniform(0, 0, -1), "yellow_blue_direction", YellowBlueDirection.BLUER),
        (_uniform(0, 0, 0), "lightness_direction", LightnessDirection.EQUAL),
    ],
)
def test_delta_sign_maps_to_exact_direction_without_perceptual_tolerance(
    comparison, field, expected
):
    diagnosis = diagnose_comparison(comparison)
    assert getattr(diagnosis.angle_diagnoses[MeasurementAngle.DEG_15], field) is expected


def test_negative_absolute_axes_with_positive_delta_are_relative_redder_yellower():
    target = Measurement(
        12,
        {angle: LabValue(50, -4, -5) for angle in MeasurementAngle},
    )
    sample = Measurement(
        13,
        {angle: LabValue(50, -2, -2) for angle in MeasurementAngle},
    )
    diagnosis = diagnose_comparison(compare_measurements(SESSION_ID, target, sample))
    angle = diagnosis.angle_diagnoses[MeasurementAngle.DEG_15]
    assert angle.delta_a == 2
    assert angle.red_green_direction is RedGreenDirection.REDDER
    assert angle.delta_b == 3
    assert angle.yellow_blue_direction is YellowBlueDirection.YELLOWER


@pytest.mark.parametrize(
    ("deltas", "expected"),
    [
        ((-3.0, 2.0, 1.0), DominantAxis.L),
        ((1.0, -3.0, 2.0), DominantAxis.A),
        ((1.0, 2.0, -3.0), DominantAxis.B),
        ((3.0, -3.0, 1.0), DominantAxis.TIE),
    ],
)
def test_dominant_axis_uses_magnitude_and_preserves_ties(deltas, expected):
    diagnosis = diagnose_comparison(_uniform(*deltas))
    assert diagnosis.angle_diagnoses[MeasurementAngle.DEG_15].dominant_axis is expected


def test_worst_angle_and_ranking_use_delta_e_with_canonical_tie_break():
    values = {
        MeasurementAngle.DEG_15: (0, 0, 0, 5),
        MeasurementAngle.DEG_25: (0, 0, 0, 3),
        MeasurementAngle.DEG_45: (0, 0, 0, 5),
        MeasurementAngle.DEG_75: (0, 0, 0, 2),
        MeasurementAngle.DEG_105: (0, 0, 0, 1),
    }
    diagnosis = diagnose_comparison(_comparison(values))
    assert diagnosis.worst_angle is MeasurementAngle.DEG_15
    assert diagnosis.angles_by_delta_e_descending == (
        MeasurementAngle.DEG_15,
        MeasurementAngle.DEG_45,
        MeasurementAngle.DEG_25,
        MeasurementAngle.DEG_75,
        MeasurementAngle.DEG_105,
    )


def test_diagnosis_preserves_exactly_five_angles_and_operational_regions():
    diagnosis = diagnose_comparison(_comparison(REAL_DELTAS))
    assert tuple(diagnosis.angle_diagnoses) == tuple(MeasurementAngle)
    assert len(diagnosis.angle_diagnoses) == 5
    assert diagnosis.front_summary.angles == (
        MeasurementAngle.DEG_15,
        MeasurementAngle.DEG_25,
    )
    assert diagnosis.mid_angle_summary.angle is MeasurementAngle.DEG_45
    assert diagnosis.flop_summary.angles == (
        MeasurementAngle.DEG_75,
        MeasurementAngle.DEG_105,
    )


def test_region_summaries_preserve_mixed_signs_instead_of_averaging():
    diagnosis = diagnose_comparison(_comparison(REAL_DELTAS))
    assert diagnosis.front_summary.lightness is LightnessDirection.DARKER
    assert diagnosis.front_summary.red_green is RedGreenDirection.REDDER
    assert diagnosis.front_summary.yellow_blue is YellowBlueDirection.MIXED
    assert diagnosis.flop_summary.lightness is LightnessDirection.LIGHTER
    assert diagnosis.flop_summary.red_green is RedGreenDirection.REDDER
    assert diagnosis.flop_summary.yellow_blue is YellowBlueDirection.YELLOWER


def test_global_sign_patterns_and_lightness_trend_are_structural():
    patterns = diagnose_comparison(_comparison(REAL_DELTAS)).global_patterns
    assert patterns.lightness is AxisSignPattern.SIGN_CROSSOVER
    assert patterns.red_green is AxisSignPattern.POSITIVE_ACROSS_ALL
    assert patterns.yellow_blue is AxisSignPattern.SIGN_CROSSOVER
    assert patterns.lightness_trend is LightnessTrend.INCREASING_WITH_ANGLE


def test_same_delta_e_does_not_define_axis_directions():
    values = {
        angle: ((1, 0, 0, 1) if angle is MeasurementAngle.DEG_15 else (-1, 0, 0, 1))
        for angle in MeasurementAngle
    }
    diagnosis = diagnose_comparison(_comparison(values))
    assert diagnosis.angle_diagnoses[MeasurementAngle.DEG_15].lightness_direction is LightnessDirection.LIGHTER
    assert diagnosis.angle_diagnoses[MeasurementAngle.DEG_25].lightness_direction is LightnessDirection.DARKER
    assert diagnosis.front_summary.lightness is LightnessDirection.MIXED


def test_real_gate_6_comparison_produces_expected_angle_diagnoses():
    diagnosis = diagnose_comparison(_comparison(REAL_DELTAS))
    expected = {
        MeasurementAngle.DEG_15: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.BLUER, DominantAxis.L),
        MeasurementAngle.DEG_25: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.L),
        MeasurementAngle.DEG_45: (LightnessDirection.DARKER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
        MeasurementAngle.DEG_75: (LightnessDirection.LIGHTER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
        MeasurementAngle.DEG_105: (LightnessDirection.LIGHTER, RedGreenDirection.REDDER, YellowBlueDirection.YELLOWER, DominantAxis.B),
    }
    for angle, expected_values in expected.items():
        actual = diagnosis.angle_diagnoses[angle]
        assert (
            actual.lightness_direction,
            actual.red_green_direction,
            actual.yellow_blue_direction,
            actual.dominant_axis,
        ) == expected_values
    assert diagnosis.worst_angle is MeasurementAngle.DEG_15
    assert diagnosis.angles_by_delta_e_descending == tuple(MeasurementAngle)


def test_diagnosis_is_deterministic_immutable_and_does_not_mutate_comparison():
    comparison = _comparison(REAL_DELTAS)
    before = tuple(comparison.angles.items())
    first = diagnose_comparison(comparison)
    second = diagnose_comparison(comparison)
    assert first == second
    assert tuple(comparison.angles.items()) == before
    assert isinstance(first, ColorDiagnosis)
    with pytest.raises(FrozenInstanceError):
        first.worst_angle = MeasurementAngle.DEG_105
    with pytest.raises(TypeError):
        first.angle_diagnoses[MeasurementAngle.DEG_15] = first.angle_diagnoses[
            MeasurementAngle.DEG_25
        ]
