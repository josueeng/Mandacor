from __future__ import annotations

import ipaddress
import logging
import select
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX systems
    fcntl = None  # type: ignore[assignment]

from mandacor.config import InstrumentConnectionConfig
from mandacor.domain.instruments import DiscoveredInstrument
from mandacor.infrastructure.instruments.byk.constants import (
    BYK_INSTRUMENT_PREFIX,
    BYK_QUERY_PREFIX,
)
from mandacor.infrastructure.instruments.byk.exceptions import DiscoveryError


logger = logging.getLogger(__name__)

SIOCGIFFLAGS = 0x8913
SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B
IFF_UP = 0x1
IFF_LOOPBACK = 0x8
IGNORED_INTERFACE_PREFIXES = ("docker", "br-", "veth", "virbr")


@dataclass(frozen=True, slots=True)
class IPv4Interface:
    name: str
    address: str
    netmask: str
    broadcast: str


@dataclass(slots=True)
class DiscoveryChannel:
    socket: Any
    local_interface: IPv4Interface | None
    destination: str
    query: bytes
    udp_port: int

    def close(self) -> None:
        self.socket.close()


def build_discovery_query(local_udp_port: int) -> bytes:
    if not 0 <= local_udp_port <= 65535:
        raise ValueError("local_udp_port must be from 0 through 65535")
    return (
        BYK_QUERY_PREFIX
        + (b"\x00" * 10)
        + struct.pack("<H", 1)
        + struct.pack("<H", local_udp_port)
    )


def is_byk_instrument_response(data: bytes) -> bool:
    return data.startswith(BYK_INSTRUMENT_PREFIX)


def calculate_broadcast(address: str, netmask: str) -> str:
    network = ipaddress.IPv4Network((address, netmask), strict=False)
    return str(network.broadcast_address)


def _ioctl_ipv4(control_socket: socket.socket, name: str, request: int) -> str:
    packed_name = struct.pack("256s", name.encode("utf-8")[:15])
    result = fcntl.ioctl(control_socket.fileno(), request, packed_name)  # type: ignore[union-attr]
    return socket.inet_ntoa(result[20:24])


def discover_ipv4_interfaces(local_interface: str | None = None) -> list[IPv4Interface]:
    """Enumerate active physical-ish IPv4 interfaces on Linux/POSIX."""
    if fcntl is None:
        raise DiscoveryError("automatic interface discovery is unavailable on this platform")
    interfaces: list[IPv4Interface] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        for _, name in socket.if_nameindex():
            explicit = local_interface in (name,)
            if not explicit and (name == "lo" or name.startswith(IGNORED_INTERFACE_PREFIXES)):
                continue
            try:
                packed_name = struct.pack("256s", name.encode("utf-8")[:15])
                flags_data = fcntl.ioctl(control.fileno(), SIOCGIFFLAGS, packed_name)
                flags = struct.unpack_from("H", flags_data, 16)[0]
                if not flags & IFF_UP or flags & IFF_LOOPBACK:
                    continue
                address = _ioctl_ipv4(control, name, SIOCGIFADDR)
                netmask = _ioctl_ipv4(control, name, SIOCGIFNETMASK)
            except OSError:
                continue
            if local_interface is not None and local_interface not in (name, address):
                continue
            interfaces.append(
                IPv4Interface(name, address, netmask, calculate_broadcast(address, netmask))
            )
    if local_interface is not None and not interfaces:
        raise DiscoveryError(f"configured local interface not found or inactive: {local_interface}")
    return interfaces


def deduplicate_instruments(
    instruments: Iterable[DiscoveredInstrument],
) -> list[DiscoveredInstrument]:
    unique: dict[tuple[object, ...], DiscoveredInstrument] = {}
    for instrument in instruments:
        key = (
            ("serial", instrument.serial)
            if instrument.serial
            else ("endpoint", instrument.ip, instrument.tcp_port)
        )
        unique.setdefault(key, instrument)
    return list(unique.values())


class BykDiscovery:
    def __init__(
        self,
        config: InstrumentConnectionConfig,
        *,
        interface_provider: Callable[[str | None], list[IPv4Interface]] = discover_ipv4_interfaces,
        socket_factory: Callable[..., Any] = socket.socket,
        select_fn: Callable[..., tuple[Sequence[Any], Sequence[Any], Sequence[Any]]] = select.select,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._interface_provider = interface_provider
        self._socket_factory = socket_factory
        self._select = select_fn
        self._monotonic = monotonic
        self._channels: list[DiscoveryChannel] = []

    @property
    def channels(self) -> tuple[DiscoveryChannel, ...]:
        return tuple(self._channels)

    def _new_channel(
        self, destination: str, interface: IPv4Interface | None
    ) -> DiscoveryChannel:
        udp_socket = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            bind_address = interface.address if interface else "0.0.0.0"
            udp_socket.bind((bind_address, 0))
            udp_socket.setblocking(False)
            local_port = udp_socket.getsockname()[1]
            return DiscoveryChannel(
                udp_socket,
                interface,
                destination,
                build_discovery_query(local_port),
                self.config.udp_port,
            )
        except BaseException:
            udp_socket.close()
            raise

    def open_channels(self, *, fallback_destination: str | None = None) -> list[DiscoveryChannel]:
        if self.config.discovery_address is not None and self.config.local_interface is None:
            return [self._new_channel(self.config.discovery_address, None)]
        if fallback_destination is not None and self.config.local_interface is None:
            return [self._new_channel(fallback_destination, None)]
        interfaces = self._interface_provider(self.config.local_interface)
        if self.config.discovery_address is not None:
            selected = interfaces[0] if len(interfaces) == 1 else None
            return [self._new_channel(self.config.discovery_address, selected)]
        if fallback_destination is not None:
            selected = interfaces[0] if len(interfaces) == 1 else None
            return [self._new_channel(fallback_destination, selected)]
        if interfaces:
            return [self._new_channel(interface.broadcast, interface) for interface in interfaces]
        raise DiscoveryError("no suitable IPv4 interface or discovery address available")

    def discover(self) -> list[DiscoveredInstrument]:
        self.close()
        self._channels = self.open_channels()
        logger.debug(
            "BYK discovery channels",
            extra={
                "destinations": [channel.destination for channel in self._channels],
                "interfaces": [
                    channel.local_interface.name if channel.local_interface else None
                    for channel in self._channels
                ],
            },
        )
        for channel in self._channels:
            channel.socket.sendto(channel.query, (channel.destination, channel.udp_port))

        deadline = self._monotonic() + self.config.discovery_timeout
        instruments: list[DiscoveredInstrument] = []
        while True:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break
            readable, _, _ = self._select(
                [channel.socket for channel in self._channels], [], [], remaining
            )
            if not readable:
                break
            for ready_socket in readable:
                try:
                    data, address = ready_socket.recvfrom(4096)
                except BlockingIOError:
                    continue
                if not is_byk_instrument_response(data):
                    continue
                source_ip, source_port = address[0], address[1]
                logger.info(
                    "BYK instrument discovered",
                    extra={"response_ip": source_ip, "response_port": source_port},
                )
                instruments.append(
                    DiscoveredInstrument(
                        manufacturer="BYK",
                        model=None,
                        serial=None,
                        ip=source_ip,
                        tcp_port=self.config.tcp_port,
                        udp_port=self.config.udp_port,
                        source="UDP BYKINSTRUMENT",
                    )
                )
        return deduplicate_instruments(instruments)

    def take_channels(self) -> list[DiscoveryChannel]:
        channels, self._channels = self._channels, []
        return channels

    def close(self) -> None:
        channels, self._channels = self._channels, []
        for channel in channels:
            try:
                channel.close()
            except OSError:
                pass
