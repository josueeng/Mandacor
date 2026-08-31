from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from mandacor.application.adjustment_workflow import AdjustmentWorkflow
from mandacor.application.measurement_wait import (
    MeasurementIdentity,
    MeasurementSnapshot,
    NewMeasurementTimeoutError,
)
from mandacor.domain.adjustments import (
    AdjustmentComponent,
    AdjustmentError,
    AdjustmentHistory,
    AdjustmentLifecycle,
    plan_adjustment,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle
from mandacor.domain.pigments import FinishType, PaintContext, PaintSystem, build_skylack_knowledge_base
from mandacor.domain.sessions import ColorSession


SESSION_ID = uuid.UUID("917cf08a-565b-43f9-b424-14a3787d79c7")


def _measurement(measurement_id):
    return Measurement(
        measurement_id,
        {angle: LabValue(50 + measurement_id / 10, 1, -1) for angle in MeasurementAngle},
        guid=f"guid-{measurement_id}",
        instrument_serial="BYK-1",
    )


def _session():
    return ColorSession.create("BYK-1", uuid_factory=lambda: SESSION_ID).with_target(
        _measurement(12)
    ).with_sample(_measurement(13))


def _pending(session=None):
    return plan_adjustment(
        session or _session(),
        PaintContext(PaintSystem.POLYESTER_BASECOAT, FinishType.METALLIC),
        "450",
        (AdjustmentComponent("BP226", "0.10"),),
        "operator reason",
        build_skylack_knowledge_base(),
    )


def _snapshot():
    return MeasurementSnapshot(
        frozenset({MeasurementIdentity("BYK-1", 13, "guid-13")}),
        "BYK-1",
        datetime.now(timezone.utc),
        uuid.uuid4(),
    )


class FakeOperations:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.snapshots = []

    def create_measurement_snapshot(self):
        snapshot = _snapshot()
        self.snapshots.append(snapshot)
        return snapshot

    def wait_for_new_measurement(self, snapshot, **kwargs):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeRepository:
    def __init__(self):
        self.saved = []
        self.cleared = []

    def save(self, pending):
        self.saved.append(pending)

    def clear(self, adjustment_id):
        self.cleared.append(adjustment_id)


def _timeout():
    return NewMeasurementTimeoutError(elapsed=5, known_count=1, last_observed_count=1, poll_count=5)


def test_confirm_applied_persists_pending_before_after_capture():
    repository = FakeRepository()
    workflow = AdjustmentWorkflow(FakeOperations([]), pending_repository=repository)
    applied = workflow.confirm_applied(_pending())
    assert applied.lifecycle is AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER
    assert repository.saved == [applied]
    assert repository.cleared == []


def test_applied_adjustment_survives_timeout_without_session_or_quantity_change():
    operations = FakeOperations([_timeout()])
    repository = FakeRepository()
    workflow = AdjustmentWorkflow(operations, pending_repository=repository)
    session = _session()
    applied = workflow.confirm_applied(_pending(session))
    request = workflow.prepare_after_capture(applied)
    with pytest.raises(NewMeasurementTimeoutError):
        workflow.capture_after(session, AdjustmentHistory(), request, timeout=5)
    assert session.sample is applied.before
    assert applied.components[0].quantity_g.as_tuple() == _pending().components[0].quantity_g.as_tuple()
    assert repository.saved == [applied]
    assert repository.cleared == []


def test_retry_uses_same_adjustment_id_and_does_not_duplicate_quantity():
    operations = FakeOperations([_timeout(), _measurement(14)])
    workflow = AdjustmentWorkflow(operations)
    session = _session()
    applied = workflow.confirm_applied(_pending(session))
    first = workflow.prepare_after_capture(applied)
    with pytest.raises(NewMeasurementTimeoutError):
        workflow.capture_after(session, AdjustmentHistory(), first)
    retry = workflow.retry_after_capture(applied)
    result = workflow.capture_after(session, AdjustmentHistory(), retry)
    assert retry.pending.adjustment_id == first.pending.adjustment_id
    assert result.trial.adjustment_id == applied.adjustment_id
    assert len(result.trial.components) == 1
    assert str(result.trial.components[0].quantity_g) == "0.10"


def test_success_is_atomic_updates_sample_preserves_target_and_appends_once():
    repository = FakeRepository()
    operations = FakeOperations([_measurement(14)])
    workflow = AdjustmentWorkflow(operations, pending_repository=repository)
    session = _session()
    target = session.target
    applied = workflow.confirm_applied(_pending(session))
    result = workflow.capture_after(
        session,
        AdjustmentHistory(),
        workflow.prepare_after_capture(applied),
    )
    assert result.session.target is target
    assert result.session.sample is result.measurement
    assert result.trial.before is session.sample
    assert result.trial.after is result.measurement
    assert result.history.trials == (result.trial,)
    assert repository.cleared == []
    workflow.acknowledge_completed(applied.adjustment_id)
    assert repository.cleared == [applied.adjustment_id]


def test_snapshot_measurement_cannot_be_used_as_after():
    operations = FakeOperations([_measurement(13)])
    workflow = AdjustmentWorkflow(operations)
    session = _session()
    applied = workflow.confirm_applied(_pending(session))
    with pytest.raises(AdjustmentError, match="snapshot"):
        workflow.capture_after(
            session,
            AdjustmentHistory(),
            workflow.prepare_after_capture(applied),
        )
    assert session.sample.measurement_id == 13


def test_completed_adjustment_cannot_be_completed_twice():
    operations = FakeOperations([_measurement(14), _measurement(15)])
    workflow = AdjustmentWorkflow(operations)
    session = _session()
    applied = workflow.confirm_applied(_pending(session))
    first = workflow.capture_after(
        session, AdjustmentHistory(), workflow.prepare_after_capture(applied)
    )
    with pytest.raises(AdjustmentError, match="already completed"):
        workflow.capture_after(
            first.session,
            first.history,
            workflow.retry_after_capture(applied),
        )


def test_target_or_current_sample_change_blocks_completion():
    operations = FakeOperations([_measurement(14), _measurement(15)])
    workflow = AdjustmentWorkflow(operations)
    original = _session()
    applied = workflow.confirm_applied(_pending(original))
    request = workflow.prepare_after_capture(applied)
    changed_sample = original.with_sample(_measurement(99))
    with pytest.raises(AdjustmentError, match="current sample changed"):
        workflow.capture_after(changed_sample, AdjustmentHistory(), request)
