from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

import pytest

from mandacor.application.measurement_wait import (
    MeasurementIdentity,
    MeasurementSnapshot,
    MeasurementWaitCancelledError,
    MeasurementWaitService,
    NewMeasurementTimeoutError,
)
from mandacor.application.sample_capture import (
    CaptureSampleService,
    ExistingMeasurementCannotBeSampleError,
)
from mandacor.domain.instruments import InstrumentInfo
from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    LabValue,
    Measurement,
    MeasurementAngle,
    MeasurementReference,
)
from mandacor.domain.sessions import (
    ColorSession,
    InvalidSessionStateError,
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


def _target_session(target_id: int = 12) -> ColorSession:
    return ColorSession.create("instrument-A", now=lambda: NOW).with_target(
        _measurement(target_id)
    )


def _snapshot(*ids: int) -> MeasurementSnapshot:
    return MeasurementSnapshot(
        frozenset(
            MeasurementIdentity("instrument-A", item, f"guid-{item}") for item in ids
        ),
        "instrument-A",
        NOW,
        uuid.uuid4(),
    )


class _FakeOperations:
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
        return _measurement(12)


def _service(operations):
    return CaptureSampleService(
        operations,
        instrument_serial="instrument-A",
        monotonic=iter([20.0, 21.5]).__next__,
    )


def test_target_captured_session_has_no_sample():
    session = _target_session()
    assert session.target.measurement_id == 12
    assert session.sample is None
    assert session.state is SessionState.TARGET_CAPTURED


def test_capture_sample_requires_target_before_snapshot():
    operations = _FakeOperations(_snapshot(1, 2, 3), _measurement(4))
    service = _service(operations)
    session = ColorSession.create("instrument-A", now=lambda: NOW)
    with pytest.raises(InvalidSessionStateError, match="target"):
        service.prepare_sample_capture(session)
    assert operations.snapshot_calls == 0


def test_prepare_sample_creates_snapshot_and_explicit_waiting_state():
    operations = _FakeOperations(_snapshot(1, 2, 12), _measurement(13))
    session = _target_session()
    request = _service(operations).prepare_sample_capture(session)
    assert request.base_session is session
    assert request.waiting_session.state is SessionState.WAITING_FOR_SAMPLE
    assert request.waiting_session.target is session.target
    assert request.waiting_session.sample is None
    assert operations.snapshot_calls == 1


def test_capture_sample_assigns_new_measurement_and_preserves_target_and_identity():
    operations = _FakeOperations(_snapshot(1, 2, 12), _measurement(15))
    service = _service(operations)
    original = _target_session()
    request = service.prepare_sample_capture(original)
    result = service.capture_sample(original, request)
    assert operations.latest_calls == 0
    assert operations.wait_calls[0][0] is request.snapshot
    assert original.sample is None
    assert result.session.target is original.target
    assert result.session.sample is result.measurement
    assert result.measurement.measurement_id == 15
    assert result.session.session_id == original.session_id
    assert result.session.created_at == original.created_at
    assert result.session.state is SessionState.READY_FOR_COMPARISON
    assert result.elapsed == pytest.approx(1.5)


def test_capture_sample_rejects_measurement_present_in_snapshot_including_target():
    operations = _FakeOperations(_snapshot(1, 2, 12), _measurement(12))
    service = _service(operations)
    original = _target_session()
    request = service.prepare_sample_capture(original)
    with pytest.raises(ExistingMeasurementCannotBeSampleError):
        service.capture_sample(original, request)
    assert original.target.measurement_id == 12
    assert original.sample is None


@pytest.mark.parametrize(
    "error",
    [
        NewMeasurementTimeoutError(
            elapsed=1.0, known_count=3, last_observed_count=3, poll_count=2
        ),
        MeasurementWaitCancelledError("cancelled"),
    ],
)
def test_failed_initial_sample_capture_preserves_target_and_no_sample(error):
    service = _service(_FakeOperations(_snapshot(1, 2, 12), error))
    original = _target_session()
    request = service.prepare_sample_capture(original)
    with pytest.raises(type(error)):
        service.capture_sample(
            original, request, cancellation=threading.Event()
        )
    assert original.target.measurement_id == 12
    assert original.sample is None
    assert original.state is SessionState.TARGET_CAPTURED


def test_sample_recapture_replaces_only_sample():
    original = _target_session().with_sample(_measurement(13))
    operations = _FakeOperations(_snapshot(1, 12, 13), _measurement(14))
    service = _service(operations)
    result = service.capture_sample(
        original, service.prepare_sample_capture(original)
    )
    assert result.session.target is original.target
    assert result.session.sample.measurement_id == 14
    assert result.session.session_id == original.session_id
    assert result.replaced_existing_sample is True


@pytest.mark.parametrize(
    "error",
    [
        NewMeasurementTimeoutError(
            elapsed=1.0, known_count=3, last_observed_count=3, poll_count=2
        ),
        MeasurementWaitCancelledError("cancelled"),
        IncompleteMeasurementError("never stabilized"),
    ],
)
def test_failed_sample_recapture_preserves_target_and_previous_sample(error):
    original = _target_session().with_sample(_measurement(13))
    service = _service(_FakeOperations(_snapshot(1, 12, 13), error))
    request = service.prepare_sample_capture(original)
    with pytest.raises(type(error)):
        service.capture_sample(original, request)
    assert original.target.measurement_id == 12
    assert original.sample.measurement_id == 13
    assert original.state is SessionState.READY_FOR_COMPARISON


@pytest.mark.parametrize(
    ("target", "sample", "state"),
    [
        (None, None, SessionState.TARGET_CAPTURED),
        (None, _measurement(2), SessionState.READY_FOR_COMPARISON),
        (_measurement(1), None, SessionState.READY_FOR_COMPARISON),
    ],
)
def test_impossible_session_states_are_rejected(target, sample, state):
    with pytest.raises(ValueError, match="inconsistent"):
        ColorSession(uuid.uuid4(), NOW, "instrument-A", target, sample, state)


def test_capture_request_cannot_be_reused_after_session_changes():
    original = _target_session()
    operations = _FakeOperations(_snapshot(12), _measurement(14))
    service = _service(operations)
    request = service.prepare_sample_capture(original)
    changed = original.with_sample(_measurement(13))
    with pytest.raises(ValueError, match="changed"):
        service.capture_sample(changed, request)


class _FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def wait(self, seconds, cancellation):
        self.value += seconds
        return False


class _RaceAdapter:
    def __init__(self):
        self.polls = [
            [MeasurementReference(12, "guid-12")],
            [MeasurementReference(12, "guid-12"), MeasurementReference(13, "guid-13")],
            [MeasurementReference(12, "guid-12"), MeasurementReference(13, "guid-13")],
        ]
        self.last = []
        self.retrieves = [
            IncompleteMeasurementError("published before complete"),
            _measurement(13),
        ]

    def list_measurements(self):
        if self.polls:
            self.last = self.polls.pop(0)
        return self.last

    def get_measurement(self, measurement_id):
        result = self.retrieves.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _WaitFacade:
    def __init__(self, service):
        self.service = service

    def create_measurement_snapshot(self):
        return self.service.create_snapshot()

    def wait_for_new_measurement(self, snapshot, **options):
        return self.service.wait_for_new_measurement(snapshot, **options)


def test_capture_sample_reuses_same_id_stabilization_retry():
    clock = _FakeClock()
    adapter = _RaceAdapter()
    wait = MeasurementWaitService(
        adapter,
        InstrumentInfo("BYK", "192.0.2.1", serial="instrument-A"),
        monotonic=clock.monotonic,
        waiter=clock.wait,
        now=lambda: NOW,
    )
    service = CaptureSampleService(
        _WaitFacade(wait),
        instrument_serial="instrument-A",
        monotonic=clock.monotonic,
    )
    original = _target_session()
    result = service.capture_sample(
        original,
        service.prepare_sample_capture(original),
        timeout=5.0,
        poll_interval=0.5,
    )
    assert result.session.target.measurement_id == 12
    assert result.session.sample.measurement_id == 13
    assert adapter.retrieves == []
