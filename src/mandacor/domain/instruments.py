from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredInstrument:
    """Manufacturer-neutral identity observed during network discovery."""

    manufacturer: str
    ip: str
    tcp_port: int
    udp_port: int | None = None
    model: str | None = None
    serial: str | None = None
    source: str | None = None


@dataclass(frozen=True, slots=True)
class InstrumentInfo:
    """Manufacturer-neutral information returned by a connected instrument."""

    manufacturer: str
    ip: str
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None

