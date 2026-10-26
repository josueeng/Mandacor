from __future__ import annotations

import uuid

import pytest

from mandacor.domain.comparison import compare_measurements
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle
from mandacor.domain.trial_assessment import (
    AngleChange,
    AssessedAxis,
    AxisChange,
    TrialVerdict,
    assess_trial,
)


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")
TARGET = Measurement(1, {angle: LabValue(50, 0, 0) for angle in MeasurementAngle}, guid="t")


def _measurement(measurement_id, lab):
    per_angle = lab if isinstance(lab, dict) else {angle: lab for angle in MeasurementAngle}
    return Measurement(measurement_id, per_angle, guid=f"guid-{measurement_id}")


def _assess(before_lab, after_lab, **kwargs):
    before = compare_measurements(SESSION_ID, TARGET, _measurement(2, before_lab))
    after = compare_measurements(SESSION_ID, TARGET, _measurement(3, after_lab))
    return assess_trial(before, after, **kwargs)


def _axis(assessment, angle, axis):
    return next(item for item in assessment.by_angle[angle].axes if item.axis is axis)


def test_closer_on_all_angles_is_improved():
    result = _assess(LabValue(50, 2, 0), LabValue(50, 0.5, 0))

    assert result.verdict is TrialVerdict.IMPROVED
    assert result.worsened_angles == ()
    assert len(result.improved_angles) == 5
    assert _axis(result, MeasurementAngle.DEG_45, AssessedAxis.A).change is AxisChange.IMPROVED


def test_farther_on_all_angles_is_worsened_by_wrong_direction():
    result = _assess(LabValue(50, 1, 0), LabValue(50, 2, 0))

    assert result.verdict is TrialVerdict.WORSENED
    assert result.wrong_direction_detected
    assert not result.overshoot_detected
    axis = _axis(result, MeasurementAngle.DEG_15, AssessedAxis.A)
    assert axis.change is AxisChange.WORSENED_WRONG_DIRECTION
    assert not axis.crossed_target


def test_crossing_the_target_and_ending_farther_is_overshoot():
    result = _assess(LabValue(50, 1, 0), LabValue(50, -1.5, 0))

    assert result.verdict is TrialVerdict.WORSENED
    assert result.overshoot_detected
    axis = _axis(result, MeasurementAngle.DEG_45, AssessedAxis.A)
    assert axis.change is AxisChange.WORSENED_OVERSHOOT
    assert axis.crossed_target


def test_crossing_the_target_but_ending_closer_is_improved_and_flagged():
    result = _assess(LabValue(50, 2, 0), LabValue(50, -0.5, 0))

    axis = _axis(result, MeasurementAngle.DEG_45, AssessedAxis.A)
    assert result.verdict is TrialVerdict.IMPROVED
    assert axis.change is AxisChange.IMPROVED
    assert axis.crossed_target


def test_worst_angle_growth_means_worsened_even_if_other_angles_improve():
    before = {angle: LabValue(50, 1, 0) for angle in MeasurementAngle}
    after = {angle: LabValue(50, 0.2, 0) for angle in MeasurementAngle}
    after[MeasurementAngle.DEG_15] = LabValue(48, 0, 0)

    result = _assess(before, after)

    assert result.verdict is TrialVerdict.WORSENED
    assert result.worsened_angles == (MeasurementAngle.DEG_15,)
    assert result.worst_delta_e_after == pytest.approx(2.0)


def test_some_angles_better_and_some_worse_without_worst_growth_is_mixed():
    before = {angle: LabValue(50, 1, 0) for angle in MeasurementAngle}
    before[MeasurementAngle.DEG_105] = LabValue(47, 0, 0)
    after = dict(before)
    after[MeasurementAngle.DEG_15] = LabValue(50, 1.6, 0)
    after[MeasurementAngle.DEG_105] = LabValue(48, 0, 0)

    result = _assess(before, after)

    assert result.verdict is TrialVerdict.MIXED
    assert result.by_angle[MeasurementAngle.DEG_15].change is AngleChange.WORSENED
    assert result.by_angle[MeasurementAngle.DEG_105].change is AngleChange.IMPROVED


def test_changes_inside_noise_are_unchanged():
    result = _assess(LabValue(50, 1, 0), LabValue(50, 1.1, 0))

    assert result.verdict is TrialVerdict.UNCHANGED
    assert _axis(result, MeasurementAngle.DEG_25, AssessedAxis.A).change is AxisChange.UNCHANGED


def test_noise_limits_are_configurable_and_validated():
    result = _assess(LabValue(50, 1, 0), LabValue(50, 1.1, 0), delta_e_noise=0.05, axis_noise=0.05)
    assert result.verdict is TrialVerdict.WORSENED

    with pytest.raises(ValueError):
        _assess(LabValue(50, 1, 0), LabValue(50, 1, 0), delta_e_noise=-1)
