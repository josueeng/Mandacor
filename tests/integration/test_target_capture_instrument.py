from __future__ import annotations

import os

import pytest

from mandacor.application.measurement_wait import (
    MeasurementWaitService,
    NewMeasurementTimeoutError,
)
from mandacor.application.target_capture import CaptureTargetService
from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle
from mandacor.domain.sessions import ColorSession, SessionState
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


INSTRUMENT_IP = os.environ.get("MANDACOR_INSTRUMENT_IP")


def _manual_config() -> InstrumentConnectionConfig:
    if not INSTRUMENT_IP:
        pytest.skip("set MANDACOR_INSTRUMENT_IP for Gate 4 bench tests")
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


def _capture_service(adapter, info):
    return CaptureTargetService(
        _WaitFacade(MeasurementWaitService(adapter, info)),
        instrument_serial=info.serial,
    )


@pytest.mark.instrument
def test_real_target_timeout_keeps_new_session_without_target():
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        session = ColorSession.create(info.serial)
        service = _capture_service(adapter, info)
        request = service.prepare_target_capture(session)
        with pytest.raises(NewMeasurementTimeoutError) as captured:
            service.capture_target(
                session,
                request,
                timeout=5.0,
                poll_interval=0.5,
            )
        assert session.target is None
        assert session.state is SessionState.WAITING_FOR_TARGET
        assert adapter.heartbeat_running
        print(
            {
                "session_id": str(session.session_id),
                "snapshot_ids": sorted(request.snapshot.known_ids),
                "target_before": None,
                "target_after": None,
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
def test_real_new_measurement_is_explicitly_captured_as_target():
    if os.environ.get("MANDACOR_INTERACTIVE_TARGET") != "1":
        pytest.skip("set MANDACOR_INTERACTIVE_TARGET=1 for target capture bench test")
    adapter = BykInstrumentAdapter(_manual_config())
    try:
        adapter.connect()
        info = adapter.get_info()
        session = ColorSession.create(info.serial)
        service = _capture_service(adapter, info)
        request = service.prepare_target_capture(session)
        print(
            "GATE 4 — faça UMA leitura da COR ALVO agora. "
            f"Session: {session.session_id}; snapshot IDs: {sorted(request.snapshot.known_ids)}",
            flush=True,
        )
        result = service.capture_target(
            session,
            request,
            timeout=300.0,
            poll_interval=0.5,
        )
        assert session.target is None
        assert result.session.session_id == session.session_id
        assert result.session.target is result.measurement
        assert result.session.state is SessionState.TARGET_CAPTURED
        assert result.measurement.measurement_id not in request.snapshot.known_ids
        assert set(result.measurement.angles) == set(MeasurementAngle)
        assert len(result.measurement.angles) * 3 == 15
        assert adapter.heartbeat_running
        print(
            {
                "session_id": str(result.session.session_id),
                "target_id": result.measurement.measurement_id,
                "target_guid": result.measurement.guid,
                "angles": len(result.measurement.angles),
                "lab_values": len(result.measurement.angles) * 3,
                "heartbeat_running": True,
            },
            flush=True,
        )
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running
