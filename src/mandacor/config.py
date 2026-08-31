from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from ipaddress import AddressValueError, IPv4Address

from mandacor.infrastructure.instruments.byk.constants import (
    DEFAULT_CONNECTION_TIMEOUT_SECONDS,
    DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_TCP_PORT,
    DEFAULT_UDP_PORT,
)
from mandacor.infrastructure.instruments.byk.exceptions import InvalidInstrumentAddressError


class ConnectionMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS = 60.0
DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_MAX_TRANSIENT_POLL_ERRORS = 2
DEFAULT_CANDIDATE_STABILIZATION_RETRIES = 5
DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("api host cannot be empty")
        if not isinstance(self.port, int) or isinstance(self.port, bool) or not 1 <= self.port <= 65535:
            raise ValueError("api port must be an integer from 1 through 65535")
        object.__setattr__(self, "cors_origins", tuple(self.cors_origins))
        if "*" in self.cors_origins:
            raise ValueError("wildcard CORS origin is not allowed")


def validate_ipv4_address(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInstrumentAddressError(value, field_name=field_name)
    try:
        address = IPv4Address(value.strip())
    except (AddressValueError, ValueError) as error:
        raise InvalidInstrumentAddressError(value, field_name=field_name) from error
    return str(address)


@dataclass(frozen=True, slots=True)
class InstrumentConnectionConfig:
    mode: ConnectionMode = ConnectionMode.AUTO
    instrument_ip: str | None = None
    last_known_instrument_ip: str | None = None
    discovery_address: str | None = None
    local_interface: str | None = None
    tcp_port: int = DEFAULT_TCP_PORT
    udp_port: int = DEFAULT_UDP_PORT
    discovery_timeout: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS
    connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT_SECONDS
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    measurement_wait_timeout: float = DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS
    measurement_poll_interval: float = DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS
    max_transient_poll_errors: int = DEFAULT_MAX_TRANSIENT_POLL_ERRORS
    candidate_stabilization_retries: int = DEFAULT_CANDIDATE_STABILIZATION_RETRIES
    candidate_stabilization_interval: float = (
        DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS
    )

    def __post_init__(self) -> None:
        mode = self.mode if isinstance(self.mode, ConnectionMode) else ConnectionMode(self.mode)
        object.__setattr__(self, "mode", mode)
        for name in ("instrument_ip", "last_known_instrument_ip", "discovery_address"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, validate_ipv4_address(value, field_name=name))
        if mode is ConnectionMode.MANUAL and self.instrument_ip is None:
            raise InvalidInstrumentAddressError(None, field_name="instrument_ip")
        for name in ("tcp_port", "udp_port"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 65535:
                raise ValueError(f"{name} must be an integer from 1 through 65535")
        for name in (
            "discovery_timeout",
            "connection_timeout",
            "heartbeat_interval",
            "measurement_wait_timeout",
            "measurement_poll_interval",
            "candidate_stabilization_interval",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if (
            not isinstance(self.max_transient_poll_errors, int)
            or isinstance(self.max_transient_poll_errors, bool)
            or self.max_transient_poll_errors < 0
        ):
            raise ValueError("max_transient_poll_errors must be a non-negative integer")
        if (
            not isinstance(self.candidate_stabilization_retries, int)
            or isinstance(self.candidate_stabilization_retries, bool)
            or self.candidate_stabilization_retries < 0
        ):
            raise ValueError(
                "candidate_stabilization_retries must be a non-negative integer"
            )

    @property
    def auto_discovery(self) -> bool:
        return self.mode is ConnectionMode.AUTO
