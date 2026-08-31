from __future__ import annotations

import json
from pathlib import Path

import pytest

from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "byk"


@pytest.mark.instrument
def test_modular_auto_discovery_connect_info_disconnect():
    adapter = BykInstrumentAdapter(InstrumentConnectionConfig(discovery_timeout=4.0))
    try:
        adapter.connect()
        info = adapter.get_info()
        assert info.model == "MicroTriColor"
        assert info.firmware == "1.2.0.24448"
        assert adapter.heartbeat_running
    finally:
        adapter.disconnect()
    assert not adapter.is_connected()
    assert not adapter.heartbeat_running


@pytest.mark.instrument
def test_modular_manual_connect_info_disconnect():
    metadata = json.loads((FIXTURES / "CAPTURE_METADATA.json").read_text(encoding="utf-8"))
    config = InstrumentConnectionConfig(
        mode=ConnectionMode.MANUAL,
        instrument_ip=metadata["discovery_source_ip"],
    )
    adapter = BykInstrumentAdapter(config)
    try:
        adapter.connect()
        info = adapter.get_info()
        assert info.ip == metadata["discovery_source_ip"]
        assert info.model == "MicroTriColor"
        assert info.firmware == "1.2.0.24448"
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running

