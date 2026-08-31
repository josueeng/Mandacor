from __future__ import annotations

from pathlib import Path

from mandacor.config import InstrumentConnectionConfig
from mandacor.domain.instruments import DiscoveredInstrument
from mandacor.infrastructure.instruments.byk.discovery import (
    BykDiscovery,
    IPv4Interface,
    build_discovery_query,
    calculate_broadcast,
    deduplicate_instruments,
    is_byk_instrument_response,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "byk"


def test_broadcast_uses_real_netmask():
    assert calculate_broadcast("192.168.10.17", "255.255.255.0") == "192.168.10.255"
    assert calculate_broadcast("192.168.10.17", "255.255.254.0") == "192.168.11.255"
    assert calculate_broadcast("10.4.5.6", "255.255.0.0") == "10.4.255.255"


def test_new_bykquery_matches_real_capture():
    captured = (FIXTURES / "discovery" / "BYKQUERY.bin").read_bytes()
    captured_port = int.from_bytes(captured[-2:], "little")
    assert build_discovery_query(captured_port) == captured


def test_real_bykinstrument_is_detected():
    captured = (FIXTURES / "discovery" / "BYKINSTRUMENT.bin").read_bytes()
    assert is_byk_instrument_response(captured)
    assert not is_byk_instrument_response(b"NOT-BYK")


def test_duplicate_discoveries_are_removed_by_endpoint():
    first = DiscoveredInstrument("BYK", "192.0.2.10", 6000)
    duplicate = DiscoveredInstrument("BYK", "192.0.2.10", 6000, source="second")
    other = DiscoveredInstrument("BYK", "192.0.2.11", 6000)
    assert deduplicate_instruments([first, duplicate, other]) == [first, other]


class _FakeUdpSocket:
    def __init__(self, response):
        self.response = response
        self.sent = []
        self.closed = False

    def setsockopt(self, *args):
        pass

    def bind(self, address):
        self.bound = address

    def setblocking(self, value):
        self.blocking = value

    def getsockname(self):
        return (self.bound[0], 43210)

    def sendto(self, data, address):
        self.sent.append((data, address))

    def recvfrom(self, size):
        return self.response

    def close(self):
        self.closed = True


def test_discovery_returns_recvfrom_source_ip():
    fixture = (FIXTURES / "discovery" / "BYKINSTRUMENT.bin").read_bytes()
    fake_socket = _FakeUdpSocket((fixture, ("198.51.100.44", 6002)))
    select_calls = 0

    def fake_select(readable, *_):
        nonlocal select_calls
        select_calls += 1
        return ([fake_socket], [], []) if select_calls == 1 else ([], [], [])

    interface = IPv4Interface("eth-test", "198.51.100.10", "255.255.255.0", "198.51.100.255")
    discovery = BykDiscovery(
        InstrumentConnectionConfig(discovery_timeout=0.01),
        interface_provider=lambda _: [interface],
        socket_factory=lambda *_: fake_socket,
        select_fn=fake_select,
    )
    instruments = discovery.discover()
    assert [instrument.ip for instrument in instruments] == ["198.51.100.44"]
    assert fake_socket.sent[0][1] == ("198.51.100.255", 6002)
    discovery.close()
    assert fake_socket.closed


def test_explicit_discovery_address_does_not_require_interface_enumeration():
    fake_socket = _FakeUdpSocket((b"", ("198.51.100.1", 6002)))

    def unavailable_interfaces(_):
        raise AssertionError("interface enumeration must not run")

    discovery = BykDiscovery(
        InstrumentConnectionConfig(discovery_address="198.51.100.255"),
        interface_provider=unavailable_interfaces,
        socket_factory=lambda *_: fake_socket,
    )
    channels = discovery.open_channels()
    assert channels[0].destination == "198.51.100.255"
    assert channels[0].local_interface is None
    channels[0].close()
    assert fake_socket.closed
