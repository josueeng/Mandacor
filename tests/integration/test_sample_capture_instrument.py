from __future__ import annotations

import os

import pytest

from mandacor.application.measurement_wait import (
    MeasurementWaitService,
    NewMeasurementTimeoutError,
)
from mandacor.application.sample_capture import CaptureSampleService
from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.sessions import ColorSession, SessionState
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


INSTRUMENT_IP = os.environ.get("MANDACOR_INSTRUMENT_IP")
TARGET_ID = int(os.environ.get("MANDACOR_GATE5_TARGET_ID", "12"))


def _manual_config() -> InstrumentConnectionConfig:
    if not INSTRUMENT_IP:
        pytest.skip("set MANDACOR_INSTRUMENT_IP for Gate 5 bench tests")
    return InstrumentConnectionConfig(
        mode=ConnectionMode.MANUAL,
        instrument_ip=INSTRUMENT_IP,
    )


class _WaitFacade:
    def __init__(self, service: MeasurementWaitService):
        self._service = service

    def create_measurement_snapshot(self):
        return self._service.create_snapshot()

    def wait_for_new_measurement(self, snapshot, **options):
        return self._service.wait_for_new_measurement(snapshot, **options)


def _session_and_service(adapter, info):
    target = adapter.get_measurement(TARGET_ID)
    session = ColorSession.create(info.serial).with_target(target)
    service = CaptureSampleService(
        _WaitFacade(MeasurementWaitService(adapter, info)),
        instrument_serial=info.serial,
    )
    return session, service


@pytest.mark.instrument
def test_real_sample_timeout_preserves_target_and_empty_sample():
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        session, service = _session_and_service(adapter, info)
        target_before = session.target
        request = service.prepare_sample_capture(session)
        with pytest.raises(NewMeasurementTimeoutError) as captured:
            service.capture_sample(
                session,
                request,
                timeout=5.0,
                poll_interval=0.5,
            )
        assert session.target is target_before
        assert session.sample is None
        assert session.state is SessionState.TARGET_CAPTURED
        assert adapter.heartbeat_running
        print(
            {
                "session_id": str(session.session_id),
                "target_id": session.target.measurement_id,
                "sample_before": None,
                "sample_after": None,
                "target_unchanged": True,
                "returned_old_measurement": False,
                "elapsed": captured.value.elapsed,
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running


@pytest.mark.instrument
@pytest.mark.interactive
def test_real_new_measurement_is_captured_as_sample_without_changing_target():
    if os.environ.get("MANDACOR_INTERACTIVE_SAMPLE") != "1":
        pytest.skip("set MANDACOR_INTERACTIVE_SAMPLE=1 for sample capture bench test")
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        session, service = _session_and_service(adapter, info)
        target_before = session.target
        request = service.prepare_sample_capture(session)
        print(
            "GATE 5 — faça UMA leitura da TINTA / AMOSTRA agora. "
            f"Session: {session.session_id}; target ID: {target_before.measurement_id}; "
            f"snapshot IDs: {sorted(request.snapshot.known_ids)}",
            flush=True,
        )
        result = service.capture_sample(
            session,
            request,
            timeout=300.0,
            poll_interval=0.5,
        )
        assert result.session.session_id == session.session_id
        assert result.session.created_at == session.created_at
        assert result.session.target is target_before
        assert result.session.sample is result.measurement
        assert result.measurement.measurement_id != target_before.measurement_id
        assert result.measurement.measurement_id not in request.snapshot.known_ids
        assert result.session.state is SessionState.READY_FOR_COMPARISON
        assert set(result.measurement.angles) == set(MeasurementAngle)
        assert len(result.measurement.angles) * 3 == 15
        assert adapter.heartbeat_running
        print(
            {
                "session_id": str(result.session.session_id),
                "target_before": target_before.measurement_id,
                "target_after": result.session.target.measurement_id,
                "sample_id": result.measurement.measurement_id,
                "sample_guid": result.measurement.guid,
                "state": result.session.state.value,
                "angles": len(result.measurement.angles),
                "lab_values": len(result.measurement.angles) * 3,
                "heartbeat_running": True,
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running
