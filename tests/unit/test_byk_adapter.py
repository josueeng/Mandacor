from __future__ import annotations

import pytest

from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.instruments import DiscoveredInstrument, InstrumentInfo
from mandacor.infrastructure.instruments.byk.adapter import AdapterState, BykInstrumentAdapter
from mandacor.infrastructure.instruments.byk.exceptions import MultipleInstrumentsFoundError


class _FakeChannel:
    def close(self):
        pass


class _FakeDiscovery:
    candidates = []

    def __init__(self, config):
        self.config = config
        self._channels = [_FakeChannel()]

    @property
    def channels(self):
        return tuple(self._channels)

    def discover(self):
        return list(self.candidates)

    def take_channels(self):
        channels, self._channels = self._channels, []
        return channels

    def open_channels(self, fallback_destination=None):
        return [_FakeChannel()]

    def close(self):
        self._channels = []


class _FakeClient:
    def __init__(self, config):
        self.connected = False
        self.ip = None

    def connect(self, ip, port):
        self.ip = ip
        self.connected = True

    def disconnect(self):
        self.connected = False

    def is_connected(self):
        return self.connected

    def get_info(self):
        return InstrumentInfo("BYK", self.ip, "FixtureModel", "serial", "firmware")


class _FakeHeartbeat:
    instances = []

    def __init__(self, channels, interval):
        self.is_running = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False
        self.stopped = True


def _adapter(config):
    return BykInstrumentAdapter(
        config,
        discovery_factory=_FakeDiscovery,
        client_factory=_FakeClient,
        heartbeat_factory=_FakeHeartbeat,
    )


def test_adapter_auto_lifecycle_stops_heartbeat():
    _FakeDiscovery.candidates = [DiscoveredInstrument("BYK", "192.0.2.13", 6000)]
    _FakeHeartbeat.instances.clear()
    adapter = _adapter(InstrumentConnectionConfig())
    adapter.connect()
    assert adapter.is_connected()
    assert adapter.state is AdapterState.CONNECTED
    assert adapter.heartbeat_running
    assert adapter.get_info().ip == "192.0.2.13"
    adapter.disconnect()
    assert adapter.state is AdapterState.DISCONNECTED
    assert not adapter.is_connected()
    assert _FakeHeartbeat.instances[-1].stopped


def test_adapter_uses_manual_ip_without_discovery_result():
    _FakeDiscovery.candidates = []
    adapter = _adapter(
        InstrumentConnectionConfig(
            mode=ConnectionMode.MANUAL,
            instrument_ip="198.51.100.80",
        )
    )
    adapter.connect()
    assert adapter.get_info().ip == "198.51.100.80"
    adapter.disconnect()


def test_adapter_uses_auto_fallback_when_discovery_is_empty():
    _FakeDiscovery.candidates = []
    adapter = _adapter(InstrumentConnectionConfig(last_known_instrument_ip="203.0.113.9"))
    adapter.connect()
    assert adapter.get_info().ip == "203.0.113.9"
    adapter.disconnect()


def test_adapter_requires_selection_for_multiple_instruments():
    _FakeDiscovery.candidates = [
        DiscoveredInstrument("BYK", "192.0.2.10", 6000),
        DiscoveredInstrument("BYK", "192.0.2.11", 6000),
    ]
    adapter = _adapter(InstrumentConnectionConfig())
    with pytest.raises(MultipleInstrumentsFoundError):
        adapter.connect()
    assert not adapter.is_connected()

