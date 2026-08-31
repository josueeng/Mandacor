from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from mandacor.domain.adjustments import (
    AdjustmentComponent,
    AdjustmentError,
    AdjustmentHistory,
    AdjustmentLifecycle,
    LearningEligibility,
    OperatorTrialStatus,
    OutcomeDirection,
    VOLUME_GALLON_ML,
    VOLUME_HALF_QUARTER_ML,
    VOLUME_QUARTER_ML,
    VisualResult,
    calculate_observed_response,
    complete_adjustment_trial,
    plan_adjustment,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle
from mandacor.domain.pigments import (
    FinishType,
    PaintContext,
    PaintSystem,
    build_skylack_knowledge_base,
)
from mandacor.domain.sessions import ColorSession


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")
ADJUSTMENT_ID = uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 8, 30, 12, 30, tzinfo=timezone.utc)
CONTEXT = PaintContext(PaintSystem.POLYESTER_BASECOAT, FinishType.METALLIC)


def _measurement(measurement_id, lab, *, serial="BYK-1", guid=None):
    per_angle = lab if isinstance(lab, dict) else {angle: lab for angle in MeasurementAngle}
    return Measurement(
        measurement_id,
        per_angle,
        guid=guid or f"guid-{measurement_id}",
        instrument_serial=serial,
    )


def _session(target=None, sample=None):
    target = target or _measurement(12, LabValue(50, 0, 0))
    sample = sample or _measurement(13, LabValue(49, 2, 1))
    return ColorSession.create(
        "BYK-1", now=lambda: NOW, uuid_factory=lambda: SESSION_ID
    ).with_target(target).with_sample(sample)


def _planned(session=None, components=None, volume="450", adjustment_id=ADJUSTMENT_ID):
    return plan_adjustment(
        session or _session(),
        CONTEXT,
        volume,
        components or (AdjustmentComponent("BP226", "0.10"),),
        "operator selected correction",
        build_skylack_knowledge_base(),
        adjustment_id_factory=lambda: adjustment_id,
        now=lambda: NOW,
    )


def _applied(**kwargs):
    return _planned(**kwargs).confirm_applied(now=lambda: LATER)


def test_observed_response_is_after_minus_before_for_five_angles():
    before = _measurement(13, LabValue(50, 2, 3))
    after = _measurement(14, LabValue(51, 1.5, 2))
    result = calculate_observed_response(before, after)
    assert tuple(result) == tuple(MeasurementAngle)
    assert len(result) == 5
    for item in result.values():
        assert (item.response_l, item.response_a, item.response_b) == (1, -0.5, -1)


def test_target_is_not_used_for_observed_response_vector():
    before = _measurement(13, LabValue(50, 2, 3))
    after = _measurement(14, LabValue(51, 1.5, 2))
    expected = calculate_observed_response(before, after)
    session_a = _session(_measurement(12, LabValue(0, 0, 0)), before)
    session_b = _session(_measurement(22, LabValue(100, 50, -50)), before)
    trial_a = complete_adjustment_trial(_applied(session=session_a), after, now=lambda: LATER)
    trial_b = complete_adjustment_trial(_applied(session=session_b), after, now=lambda: LATER)
    assert trial_a.observed_response_by_angle == expected
    assert trial_b.observed_response_by_angle == expected


def test_delta_e_improvement_positive_closer_and_negative_farther():
    target = _measurement(12, LabValue(50, 0, 0))
    before = _measurement(13, LabValue(48, 0, 0))
    closer = complete_adjustment_trial(
        _applied(session=_session(target, before)),
        _measurement(14, LabValue(49, 0, 0)),
        now=lambda: LATER,
    )
    farther = complete_adjustment_trial(
        _applied(session=_session(target, before)),
        _measurement(15, LabValue(45, 0, 0)),
        now=lambda: LATER,
    )
    assert closer.outcome_by_angle[MeasurementAngle.DEG_15].delta_e_improvement == 1
    assert closer.outcome_by_angle[MeasurementAngle.DEG_15].delta_e_outcome is OutcomeDirection.IMPROVED
    assert farther.outcome_by_angle[MeasurementAngle.DEG_15].delta_e_improvement == -3
    assert farther.outcome_by_angle[MeasurementAngle.DEG_15].delta_e_outcome is OutcomeDirection.WORSENED


def test_axis_improvement_uses_absolute_error_and_good_crossover_improves():
    target = _measurement(12, LabValue(50, 0, 0))
    before = _measurement(13, LabValue(50, 2, 0))
    after = _measurement(14, LabValue(50, -0.1, 0))
    item = complete_adjustment_trial(
        _applied(session=_session(target, before)), after, now=lambda: LATER
    ).outcome_by_angle[MeasurementAngle.DEG_15]
    assert item.before_abs_delta_a == 2
    assert item.after_abs_delta_a == pytest.approx(0.1)
    assert item.improvement_a == pytest.approx(1.9)
    assert item.red_green_outcome is OutcomeDirection.IMPROVED


def test_overshoot_in_correct_direction_can_be_worsening():
    target = _measurement(12, LabValue(50, 0, 0))
    before = _measurement(13, LabValue(49, 0, 0))
    after = _measurement(14, LabValue(53, 0, 0))
    item = complete_adjustment_trial(
        _applied(session=_session(target, before)), after, now=lambda: LATER
    ).outcome_by_angle[MeasurementAngle.DEG_15]
    assert item.improvement_l == -2
    assert item.lightness_outcome is OutcomeDirection.WORSENED
    assert calculate_observed_response(before, after)[MeasurementAngle.DEG_15].response_l == 4


def test_unchanged_distance_is_mathematically_unchanged():
    target = _measurement(12, LabValue(50, 0, 0))
    before = _measurement(13, LabValue(49, 0, 0))
    after = _measurement(14, LabValue(51, 0, 0))
    item = complete_adjustment_trial(
        _applied(session=_session(target, before)), after, now=lambda: LATER
    ).outcome_by_angle[MeasurementAngle.DEG_15]
    assert item.improvement_l == 0
    assert item.lightness_outcome is OutcomeDirection.UNCHANGED


@pytest.mark.parametrize("text", ["0.05", "0.10", "0.25"])
def test_small_quantities_preserve_decimal_text(text):
    component = AdjustmentComponent("BP226", text)
    assert component.quantity_g == Decimal(text)
    assert format(component.quantity_g, "f") == text


@pytest.mark.parametrize("value", ["0", "-0.1", "NaN", "Infinity", float("nan")])
def test_invalid_quantity_is_rejected(value):
    with pytest.raises(AdjustmentError):
        AdjustmentComponent("BP226", value)


@pytest.mark.parametrize("volume", ["450", "900", "3600"])
def test_valid_volume_is_canonical_decimal_ml(volume):
    assert _planned(volume=volume).volume_ml == Decimal(volume)


@pytest.mark.parametrize("volume", [0, -1, "NaN", float("inf")])
def test_invalid_volume_is_rejected(volume):
    with pytest.raises(AdjustmentError):
        _planned(volume=volume)


def test_exact_named_volume_conversions():
    assert VOLUME_HALF_QUARTER_ML == Decimal("450")
    assert VOLUME_QUARTER_ML == Decimal("900")
    assert VOLUME_GALLON_ML == Decimal("3600")


def test_unknown_pigment_code_is_explicit_error_without_typo_correction():
    with pytest.raises(AdjustmentError, match="unknown pigment code"):
        _planned(components=(AdjustmentComponent("BP999", "0.1"),))


def test_single_and_multi_component_learning_eligibility():
    assert _planned().learning_eligibility is LearningEligibility.ISOLATED_SINGLE_COMPONENT
    mixed = _planned(components=(
        AdjustmentComponent("BP226", "0.10"),
        AdjustmentComponent("BP282", "0.50"),
    ))
    assert mixed.learning_eligibility is LearningEligibility.MIXED_COMPONENTS


def test_planned_can_cancel_but_applied_must_be_preserved_or_abandoned_explicitly():
    planned = _planned()
    assert planned.cancel_before_application().lifecycle is AdjustmentLifecycle.CANCELLED_BEFORE_APPLICATION
    applied = planned.confirm_applied(now=lambda: LATER)
    with pytest.raises(AdjustmentError):
        applied.cancel_before_application()
    abandoned = applied.abandon_after_application("operator explicitly abandoned after application")
    assert abandoned.lifecycle is AdjustmentLifecycle.ABANDONED_AFTER_APPLICATION
    assert abandoned.adjustment_id == ADJUSTMENT_ID


def test_completed_trial_preserves_ids_target_before_after_and_is_immutable():
    pending = _applied()
    after = _measurement(14, LabValue(50, 1, 0))
    trial = complete_adjustment_trial(
        pending,
        after,
        visual_result=VisualResult.BETTER,
        operator_status=OperatorTrialStatus.ACCEPTED,
        now=lambda: LATER,
    )
    assert trial.adjustment_id == ADJUSTMENT_ID
    assert trial.session_id == SESSION_ID
    assert trial.target is pending.target
    assert trial.before is pending.before
    assert trial.after is after
    assert tuple(trial.observed_response_by_angle) == tuple(MeasurementAngle)
    with pytest.raises(FrozenInstanceError):
        trial.after = pending.before
    with pytest.raises(TypeError):
        trial.outcome_by_angle[MeasurementAngle.DEG_15] = trial.outcome_by_angle[MeasurementAngle.DEG_25]


def test_after_cannot_reuse_before_identity():
    pending = _applied()
    with pytest.raises(AdjustmentError, match="new measurement"):
        complete_adjustment_trial(pending, pending.before)


def test_completed_adjustment_cannot_be_appended_twice():
    trial = complete_adjustment_trial(
        _applied(), _measurement(14, LabValue(50, 1, 0)), now=lambda: LATER
    )
    history = AdjustmentHistory().append(trial)
    with pytest.raises(AdjustmentError, match="already"):
        history.append(trial)


def test_sequential_history_preserves_chain_and_old_trials():
    session = _session()
    trial1 = complete_adjustment_trial(
        _applied(session=session), _measurement(14, LabValue(50, 1, 0)), now=lambda: LATER
    )
    session_after = session.with_sample(trial1.after)
    trial2 = complete_adjustment_trial(
        _applied(session=session_after, adjustment_id=uuid.UUID("bbbbbbbb-cccc-4ddd-8eee-ffffffffffff")),
        _measurement(15, LabValue(50, 0.5, 0)),
        now=lambda: LATER,
    )
    history = AdjustmentHistory().append(trial1).append(trial2)
    assert len(history.trials) == 2
    assert history.trials[0] is trial1
    assert history.trials[1].before is trial1.after
    assert history.trials[1].after is trial2.after
