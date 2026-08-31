from __future__ import annotations

import os
import time

import pytest

from mandacor.application.measurement_wait import (
    MeasurementWaitService,
    NewMeasurementTimeoutError,
)
from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


INSTRUMENT_IP = os.environ.get("MANDACOR_INSTRUMENT_IP")


class _CountingMeasurementAdapter:
    def __init__(self, adapter):
        self._adapter = adapter
        self.get_attempts: dict[int, int] = {}

    def list_measurements(self):
        return self._adapter.list_measurements()

    def get_measurement(self, measurement_id):
        self.get_attempts[measurement_id] = self.get_attempts.get(measurement_id, 0) + 1
        return self._adapter.get_measurement(measurement_id)


def _manual_config() -> InstrumentConnectionConfig:
    if not INSTRUMENT_IP:
        pytest.skip("set MANDACOR_INSTRUMENT_IP for Gate 3 bench tests")
    return InstrumentConnectionConfig(
        mode=ConnectionMode.MANUAL,
        instrument_ip=INSTRUMENT_IP,
    )


@pytest.mark.instrument
def test_real_wait_without_measurement_times_out_and_returns_no_old_record():
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        service = MeasurementWaitService(adapter, info)
        snapshot = service.create_snapshot()
        latest_before = max(snapshot.known_ids) if snapshot.known_ids else None
        started = time.monotonic()
        with pytest.raises(NewMeasurementTimeoutError) as captured:
            service.wait_for_new_measurement(snapshot, timeout=5.0, poll_interval=0.5)
        elapsed = time.monotonic() - started
        assert elapsed >= 5.0
        # Each real network poll has non-zero duration, so the configured interval is
        # a lower bound between polls rather than a guaranteed polls-per-second rate.
        assert captured.value.poll_count >= 2
        assert adapter.heartbeat_running
        print(
            {
                "snapshot_ids": sorted(snapshot.known_ids),
                "latest_before": latest_before,
                "returned_old_measurement": False,
                "polls": captured.value.poll_count,
                "elapsed": elapsed,
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running


@pytest.mark.instrument
@pytest.mark.interactive
def test_three_real_sequential_new_measurements_are_detected():
    if os.environ.get("MANDACOR_INTERACTIVE_MEASUREMENT") != "1":
        pytest.skip("set MANDACOR_INTERACTIVE_MEASUREMENT=1 for human measurement test")
    adapter = BykInstrumentAdapter(_manual_config())
    detected = []
    try:
        adapter.connect()
        info = adapter.get_info()
        service = MeasurementWaitService(adapter, info)
        for cycle in range(1, 4):
            snapshot = service.create_snapshot()
            print(
                f"GATE 3 CYCLE {cycle}/3 — fa\u00e7a UMA nova leitura f\u00edsica agora. "
                f"Snapshot IDs: {sorted(snapshot.known_ids)}",
                flush=True,
            )
            started = time.monotonic()
            measurement = service.wait_for_new_measurement(
                snapshot,
                # Human bench coordination can span multiple chat turns.
                timeout=300.0,
                poll_interval=0.5,
            )
            elapsed = time.monotonic() - started
            assert (measurement.measurement_id, measurement.guid) not in {
                (identity.measurement_id, identity.guid) for identity in snapshot.identities
            }
            assert set(measurement.angles) == set(MeasurementAngle)
            assert len(measurement.angles) * 3 == 15
            assert adapter.heartbeat_running
            detected.append((measurement.measurement_id, measurement.guid, elapsed))
            print(
                f"CYCLE {cycle} PASS — ID={measurement.measurement_id} "
                f"GUID={measurement.guid} elapsed={elapsed:.3f}s",
                flush=True,
            )
    finally:
        adapter.disconnect()
    assert len({(measurement_id, guid) for measurement_id, guid, _ in detected}) == 3
    assert not adapter.heartbeat_running
    print({"detected": detected, "heartbeat_leak": False}, flush=True)


@pytest.mark.instrument
@pytest.mark.interactive
def test_one_real_measurement_stabilizes_without_requesting_another():
    if os.environ.get("MANDACOR_INTERACTIVE_STABILIZATION") != "1":
        pytest.skip("set MANDACOR_INTERACTIVE_STABILIZATION=1 for stabilization bench test")
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        counting_adapter = _CountingMeasurementAdapter(adapter)
        service = MeasurementWaitService(counting_adapter, info)
        snapshot = service.create_snapshot()
        print(
            "PRE-GATE 4 — faça exatamente UMA nova leitura física agora. "
            f"Snapshot IDs: {sorted(snapshot.known_ids)}",
            flush=True,
        )
        measurement = service.wait_for_new_measurement(
            snapshot,
            timeout=300.0,
            poll_interval=0.5,
            candidate_stabilization_retries=5,
            candidate_stabilization_interval=0.5,
        )
        assert measurement.measurement_id not in snapshot.known_ids
        assert set(measurement.angles) == set(MeasurementAngle)
        assert adapter.heartbeat_running
        print(
            {
                "measurement_id": measurement.measurement_id,
                "guid": measurement.guid,
                "retrieve_attempts": counting_adapter.get_attempts[measurement.measurement_id],
                "requested_second_measurement": False,
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running
