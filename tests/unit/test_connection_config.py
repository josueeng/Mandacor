from __future__ import annotations

import json
from dataclasses import replace

import pytest

from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.infrastructure.config.json_config import JsonConfigurationRepository
from mandacor.infrastructure.instruments.byk.exceptions import InvalidInstrumentAddressError


@pytest.mark.parametrize("address", ["999.999.1.1", "abc", "192.168.1", ""])
def test_invalid_manual_ipv4_is_rejected(address):
    with pytest.raises(InvalidInstrumentAddressError):
        InstrumentConnectionConfig(mode=ConnectionMode.MANUAL, instrument_ip=address)


def test_manual_mode_requires_an_address():
    with pytest.raises(InvalidInstrumentAddressError):
        InstrumentConnectionConfig(mode=ConnectionMode.MANUAL)


def test_network_can_change_without_source_changes():
    first = InstrumentConnectionConfig(instrument_ip="192.168.1.13")
    second = replace(first, instrument_ip="192.168.0.80")
    assert first.instrument_ip == "192.168.1.13"
    assert second.instrument_ip == "192.168.0.80"


def test_json_configuration_round_trip(tmp_path):
    path = tmp_path / "mandacor.json"
    repository = JsonConfigurationRepository(path)
    config = InstrumentConnectionConfig(
        mode=ConnectionMode.MANUAL,
        instrument_ip="10.0.0.50",
        last_known_instrument_ip="10.0.0.49",
        discovery_address="10.0.1.255",
        local_interface="eth0",
        tcp_port=6100,
        udp_port=6102,
        discovery_timeout=2.5,
        connection_timeout=4.5,
        heartbeat_interval=0.8,
        measurement_wait_timeout=45.0,
        measurement_poll_interval=0.75,
        max_transient_poll_errors=3,
        candidate_stabilization_retries=4,
        candidate_stabilization_interval=0.4,
    )
    repository.save(config)
    assert repository.load() == config
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["instrument"]["connection"]["mode"] == "manual"
    assert document["instrument"]["connection"]["measurement_wait_timeout"] == 45.0
    assert document["instrument"]["connection"]["measurement_poll_interval"] == 0.75
    assert document["instrument"]["connection"]["candidate_stabilization_retries"] == 4
    assert document["instrument"]["connection"]["candidate_stabilization_interval"] == 0.4


def test_missing_configuration_uses_auto_defaults(tmp_path):
    config = JsonConfigurationRepository(tmp_path / "missing.json").load()
    assert config.mode is ConnectionMode.AUTO
    assert config.instrument_ip is None
    assert config.tcp_port == 6000
    assert config.udp_port == 6002
