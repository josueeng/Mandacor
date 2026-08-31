from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest

from mandacor.application.measurement_wait import (
    InstrumentChangedDuringWaitError,
    MeasurementWaitCancelledError,
    MeasurementWaitService,
    NewMeasurementTimeoutError,
)
from mandacor.domain.instruments import InstrumentInfo
from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    LabValue,
    Measurement,
    MeasurementAngle,
    MeasurementReference,
)
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentTimeoutError


def _reference(measurement_id: int, guid: str | None = None):
    return MeasurementReference(measurement_id, guid or f"guid-{measurement_id}")


def _measurement(
    measurement_id: int,
    guid: str | None = None,
    *,
    serial: str = "instrument-A",
):
    return Measurement(
        measurement_id,
        {angle: LabValue(float(angle), 0.1, -0.1) for angle in MeasurementAngle},
        guid=guid or f"guid-{measurement_id}",
        instrument_serial=serial,
    )


class _FakeAdapter:
    def __init__(self, polls, measurements=None):
        self.polls = list(polls)
        self.last_poll = []
        self.measurements = measurements or {}
        self.list_calls = 0
        self.get_calls = []

    def list_measurements(self):
        self.list_calls += 1
        if self.polls:
            item = self.polls.pop(0)
            if isinstance(item, BaseException):
                raise item
            self.last_poll = item
        return list(self.last_poll)

    def get_measurement(self, measurement_id):
        self.get_calls.append(measurement_id)
        result = self.measurements[measurement_id]
        if isinstance(result, list):
            result = result.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class _FakeTime:
    def __init__(self, *, cancel_event=None):
        self.value = 0.0
        self.waits = []
        self.cancel_event = cancel_event

    def monotonic(self):
        return self.value

    def wait(self, seconds, cancel_event):
        self.waits.append(seconds)
        self.value += seconds
        if self.cancel_event is not None:
            self.cancel_event.set()
            return True
        return cancel_event.is_set() if cancel_event is not None else False


def _service(adapter, clock=None, *, serial="instrument-A"):
    clock = clock or _FakeTime()
    return MeasurementWaitService(
        adapter,
        InstrumentInfo("BYK", "192.0.2.1", serial=serial),
        monotonic=clock.monotonic,
        waiter=clock.wait,
        now=lambda: datetime(2026, 8, 29, tzinfo=timezone.utc),
    ), clock


def test_snapshot_empty_list_is_lightweight_and_immutable():
    service, _ = _service(_FakeAdapter([[]]))
    snapshot = service.create_snapshot()
    assert snapshot.identities == frozenset()
    assert snapshot.known_ids == frozenset()
    assert snapshot.instrument_serial == "instrument-A"


def test_snapshot_preserves_existing_id_and_guid_identities():
    service, _ = _service(_FakeAdapter([[[ _reference(1), _reference(2), _reference(3) ][i] for i in range(3)]]))
    snapshot = service.create_snapshot()
    assert snapshot.known_ids == frozenset({1, 2, 3})
    assert {identity.guid for identity in snapshot.identities} == {"guid-1", "guid-2", "guid-3"}


def test_no_change_times_out_and_never_returns_old_latest():
    existing = [_reference(1), _reference(2), _reference(3)]
    adapter = _FakeAdapter([existing, existing, existing, existing], {3: _measurement(3)})
    service, clock = _service(adapter)
    snapshot = service.create_snapshot()
    with pytest.raises(NewMeasurementTimeoutError) as captured:
        service.wait_for_new_measurement(snapshot, timeout=1.0, poll_interval=0.4)
    assert adapter.get_calls == []
    assert captured.value.known_count == 3
    assert clock.waits == [0.4, 0.4, pytest.approx(0.2)]


def test_one_new_measurement_is_retrieved_and_validated():
    existing = [_reference(1), _reference(2), _reference(3)]
    adapter = _FakeAdapter([existing, existing + [_reference(4)]], {4: _measurement(4)})
    service, _ = _service(adapter)
    snapshot = service.create_snapshot()
    result = service.wait_for_new_measurement(snapshot, timeout=2.0, poll_interval=0.5)
    assert result.measurement_id == 4
    assert adapter.get_calls == [4]
    assert adapter.list_calls == 3


def test_new_identity_is_seen_twice_before_its_single_retrieve_attempt():
    existing = [_reference(1)]
    new_state = existing + [_reference(2)]
    adapter = _FakeAdapter([existing, new_state, new_state], {2: _measurement(2)})
    service, clock = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(), timeout=2.0, poll_interval=0.5
    )
    assert result.measurement_id == 2
    assert adapter.get_calls == [2]
    assert clock.waits == [0.5]


def test_multiple_new_measurements_returns_first_valid_by_id():
    existing = [_reference(1), _reference(2), _reference(3)]
    current = existing + [_reference(5), _reference(4)]
    adapter = _FakeAdapter([existing, current], {4: _measurement(4), 5: _measurement(5)})
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(), timeout=2.0, poll_interval=0.5
    )
    assert result.measurement_id == 4
    assert adapter.get_calls == [4]


def test_invalid_new_candidate_is_processed_once_then_valid_candidate_returns():
    existing = [_reference(1), _reference(2), _reference(3)]
    adapter = _FakeAdapter(
        [existing, existing + [_reference(4)], existing + [_reference(4), _reference(5)]],
        {
            4: IncompleteMeasurementError("synthetic invalid #4"),
            5: _measurement(5),
        },
    )
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(),
        timeout=2.0,
        poll_interval=0.5,
        candidate_stabilization_retries=0,
    )
    assert result.measurement_id == 5
    assert adapter.get_calls == [4, 5]


def test_same_candidate_is_retried_until_it_stabilizes():
    existing = [_reference(1), _reference(2), _reference(3)]
    current = existing + [_reference(4)]
    adapter = _FakeAdapter(
        [existing, current, current],
        {
            4: [
                IncompleteMeasurementError("not ready once"),
                IncompleteMeasurementError("not ready twice"),
                _measurement(4),
            ]
        },
    )
    service, clock = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(),
        timeout=5.0,
        poll_interval=0.5,
        candidate_stabilization_retries=2,
        candidate_stabilization_interval=0.25,
    )
    assert result.measurement_id == 4
    assert adapter.get_calls == [4, 4, 4]
    assert clock.waits == [0.5, 0.25, 0.25]


def test_candidate_exhausts_stabilization_retries_then_next_valid_returns():
    existing = [_reference(1), _reference(2), _reference(3)]
    with_four = existing + [_reference(4)]
    with_five = with_four + [_reference(5)]
    adapter = _FakeAdapter(
        [existing, with_four, with_four, with_five, with_five],
        {
            4: [
                IncompleteMeasurementError("not ready 1"),
                IncompleteMeasurementError("not ready 2"),
                IncompleteMeasurementError("not ready 3"),
            ],
            5: _measurement(5),
        },
    )
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(),
        timeout=5.0,
        poll_interval=0.5,
        candidate_stabilization_retries=2,
        candidate_stabilization_interval=0.25,
    )
    assert result.measurement_id == 5
    assert adapter.get_calls == [4, 4, 4, 5]


def test_removed_measurement_is_not_new():
    existing = [_reference(1), _reference(2), _reference(3)]
    adapter = _FakeAdapter(
        [existing, [_reference(1), _reference(3)], [_reference(1), _reference(3), _reference(4)]],
        {4: _measurement(4)},
    )
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(), timeout=2.0, poll_interval=0.5
    )
    assert result.measurement_id == 4
    assert adapter.get_calls == [4]


def test_duplicate_old_references_are_not_new():
    old = [_reference(1), _reference(1), _reference(2)]
    adapter = _FakeAdapter([old, old, old])
    service, _ = _service(adapter)
    with pytest.raises(NewMeasurementTimeoutError):
        service.wait_for_new_measurement(
            service.create_snapshot(), timeout=0.5, poll_interval=0.5
        )
    assert adapter.get_calls == []


def test_same_id_with_new_guid_is_a_new_identity():
    old = [MeasurementReference(3, "guid-A")]
    changed = [MeasurementReference(3, "guid-B")]
    adapter = _FakeAdapter([old, changed], {3: _measurement(3, "guid-B")})
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(), timeout=1.0, poll_interval=0.5
    )
    assert result.guid == "guid-B"


def test_missing_guid_falls_back_to_id_and_does_not_create_false_new():
    old = [MeasurementReference(3, "guid-A")]
    weaker = [MeasurementReference(3, None)]
    adapter = _FakeAdapter([old, weaker, weaker])
    service, _ = _service(adapter)
    with pytest.raises(NewMeasurementTimeoutError):
        service.wait_for_new_measurement(
            service.create_snapshot(), timeout=0.5, poll_interval=0.5
        )
    assert adapter.get_calls == []


def test_cancel_before_wait_does_not_poll():
    existing = [_reference(1)]
    adapter = _FakeAdapter([existing])
    service, _ = _service(adapter)
    snapshot = service.create_snapshot()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(MeasurementWaitCancelledError):
        service.wait_for_new_measurement(snapshot, cancellation=cancel)
    assert adapter.list_calls == 1


def test_cancel_during_wait_is_cooperative_and_fast():
    existing = [_reference(1)]
    cancel = threading.Event()
    clock = _FakeTime(cancel_event=cancel)
    adapter = _FakeAdapter([existing, existing])
    service, _ = _service(adapter, clock)
    with pytest.raises(MeasurementWaitCancelledError):
        service.wait_for_new_measurement(
            service.create_snapshot(), timeout=30.0, poll_interval=0.5, cancellation=cancel
        )
    assert clock.waits == [0.5]


def test_transient_poll_timeouts_are_bounded_and_recover():
    existing = [_reference(1)]
    adapter = _FakeAdapter(
        [
            existing,
            InstrumentTimeoutError("one"),
            InstrumentTimeoutError("two"),
            existing + [_reference(2)],
        ],
        {2: _measurement(2)},
    )
    service, _ = _service(adapter)
    result = service.wait_for_new_measurement(
        service.create_snapshot(), timeout=3.0, poll_interval=0.5, max_transient_poll_errors=2
    )
    assert result.measurement_id == 2


def test_persistent_poll_timeout_is_propagated():
    existing = [_reference(1)]
    adapter = _FakeAdapter(
        [
            existing,
            InstrumentTimeoutError("one"),
            InstrumentTimeoutError("two"),
        ]
    )
    service, _ = _service(adapter)
    with pytest.raises(InstrumentTimeoutError, match="two"):
        service.wait_for_new_measurement(
            service.create_snapshot(),
            timeout=3.0,
            poll_interval=0.5,
            max_transient_poll_errors=1,
        )


def test_snapshot_from_another_instrument_session_is_rejected():
    adapter = _FakeAdapter([[_reference(1)]])
    service_a, _ = _service(adapter, serial="instrument-A")
    service_b, _ = _service(adapter, serial="instrument-B")
    snapshot = service_a.create_snapshot()
    with pytest.raises(InstrumentChangedDuringWaitError):
        service_b.wait_for_new_measurement(snapshot)


def test_retrieved_measurement_from_other_instrument_is_rejected():
    existing = [_reference(1)]
    adapter = _FakeAdapter(
        [existing, existing + [_reference(2)]],
        {2: _measurement(2, serial="instrument-B")},
    )
    service, _ = _service(adapter, serial="instrument-A")
    with pytest.raises(InstrumentChangedDuringWaitError):
        service.wait_for_new_measurement(
            service.create_snapshot(), timeout=1.0, poll_interval=0.5
        )
