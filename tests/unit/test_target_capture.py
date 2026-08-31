from __future__ import annotations

import threading
import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from mandacor.application.measurement_wait import (
    MeasurementIdentity,
    MeasurementSnapshot,
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.application.target_capture import (
    CaptureTargetService,
    ExistingMeasurementCannotBeTargetError,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle
from mandacor.domain.sessions import (
    ColorSession,
    SessionInstrumentMismatchError,
    SessionState,
)


NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


def _measurement(measurement_id: int, *, serial: str = "instrument-A") -> Measurement:
    return Measurement(
        measurement_id,
        {angle: LabValue(float(angle), 0.1, -0.1) for angle in MeasurementAngle},
        guid=f"guid-{measurement_id}",
        instrument_serial=serial,
    )


def _snapshot(*ids: int) -> MeasurementSnapshot:
    return MeasurementSnapshot(
        frozenset(
            MeasurementIdentity("instrument-A", measurement_id, f"guid-{measurement_id}")
            for measurement_id in ids
        ),
        "instrument-A",
        NOW,
        uuid.uuid4(),
    )


class _FakeWaitOperations:
    def __init__(self, snapshot, result):
        self.snapshot = snapshot
        self.result = result
        self.snapshot_calls = 0
        self.wait_calls = []
        self.latest_calls = 0

    def create_measurement_snapshot(self):
        self.snapshot_calls += 1
        return self.snapshot

    def wait_for_new_measurement(self, snapshot, **options):
        self.wait_calls.append((snapshot, options))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result

    def get_latest_measurement(self):
        self.latest_calls += 1
        return _measurement(3)


def _service(operations):
    return CaptureTargetService(
        operations,
        instrument_serial="instrument-A",
        monotonic=iter([10.0, 11.25]).__next__,
    )


def test_new_session_has_uuid_no_target_and_explicit_state():
    session = ColorSession.create("instrument-A", now=lambda: NOW)
    assert isinstance(session.session_id, uuid.UUID)
    assert session.created_at == NOW
    assert session.instrument_serial == "instrument-A"
    assert session.target is None
    assert session.state is SessionState.WAITING_FOR_TARGET


def test_capture_target_assigns_only_new_measurement_after_prepare():
    operations = _FakeWaitOperations(_snapshot(1, 2, 3), _measurement(4))
    service = _service(operations)
    original = ColorSession.create("instrument-A", now=lambda: NOW)
    request = service.prepare_target_capture(original)
    result = service.capture_target(original, request)
    assert operations.snapshot_calls == 1
    assert operations.wait_calls[0][0] is request.snapshot
    assert operations.latest_calls == 0
    assert original.target is None
    assert result.session.target is result.measurement
    assert result.measurement.measurement_id == 4
    assert result.session.state is SessionState.TARGET_CAPTURED
    assert result.elapsed == pytest.approx(1.25)


def test_capture_target_rejects_measurement_that_existed_in_snapshot():
    operations = _FakeWaitOperations(_snapshot(1, 2, 3), _measurement(3))
    service = _service(operations)
    session = ColorSession.create("instrument-A", now=lambda: NOW)
    request = service.prepare_target_capture(session)
    with pytest.raises(ExistingMeasurementCannotBeTargetError):
        service.capture_target(session, request)
    assert session.target is None


@pytest.mark.parametrize(
    "error",
    [
        NewMeasurementTimeoutError(
            elapsed=1.0, known_count=3, last_observed_count=3, poll_count=2
        ),
        MeasurementWaitCancelledError("cancelled"),
    ],
)
def test_failed_initial_capture_keeps_session_consistent(error):
    service = _service(_FakeWaitOperations(_snapshot(1, 2, 3), error))
    session = ColorSession.create("instrument-A", now=lambda: NOW)
    request = service.prepare_target_capture(session)
    with pytest.raises(type(error)):
        service.capture_target(session, request, cancellation=threading.Event())
    assert session.target is None
    assert session.state is SessionState.WAITING_FOR_TARGET


def test_recapture_replaces_target_only_after_new_measurement():
    operations = _FakeWaitOperations(_snapshot(1, 2, 3, 4), _measurement(5))
    service = _service(operations)
    original = ColorSession.create("instrument-A", now=lambda: NOW).with_target(
        _measurement(4)
    )
    result = service.capture_target(original, service.prepare_target_capture(original))
    assert original.target.measurement_id == 4
    assert result.session.target.measurement_id == 5
    assert result.session.session_id == original.session_id


def test_failed_recapture_preserves_old_target():
    timeout = NewMeasurementTimeoutError(
        elapsed=1.0, known_count=4, last_observed_count=4, poll_count=2
    )
    service = _service(_FakeWaitOperations(_snapshot(1, 2, 3, 4), timeout))
    original = ColorSession.create("instrument-A", now=lambda: NOW).with_target(
        _measurement(4)
    )
    request = service.prepare_target_capture(original)
    with pytest.raises(NewMeasurementTimeoutError):
        service.capture_target(original, request)
    assert original.target.measurement_id == 4
    assert original.state is SessionState.TARGET_CAPTURED


def test_target_measurement_and_session_are_immutable():
    session = ColorSession.create("instrument-A", now=lambda: NOW).with_target(
        _measurement(4)
    )
    with pytest.raises(FrozenInstanceError):
        session.target = _measurement(5)
    with pytest.raises(FrozenInstanceError):
        session.target.measurement_id = 99


def test_target_instrument_must_match_session():
    session = ColorSession.create("instrument-A", now=lambda: NOW)
    with pytest.raises(SessionInstrumentMismatchError):
        session.with_target(_measurement(4, serial="instrument-B"))


def test_capture_request_cannot_be_used_with_another_session():
    operations = _FakeWaitOperations(_snapshot(1), _measurement(2))
    service = _service(operations)
    first = ColorSession.create("instrument-A", now=lambda: NOW)
    second = ColorSession.create("instrument-A", now=lambda: NOW)
    request = service.prepare_target_capture(first)
    with pytest.raises(ValueError, match="another session"):
        service.capture_target(second, request)
