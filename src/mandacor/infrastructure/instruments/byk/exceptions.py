from __future__ import annotations


class InstrumentError(Exception):
    """Base error for instrument operations."""


class InstrumentNotFoundError(InstrumentError):
    pass


class MultipleInstrumentsFoundError(InstrumentError):
    pass


class InstrumentConnectionError(InstrumentError):
    def __init__(self, address: str, port: int) -> None:
        self.address = address
        self.port = port
        super().__init__(f"could not connect to instrument at {address}:{port}")


class InstrumentTimeoutError(InstrumentError):
    pass


class InstrumentProtocolError(InstrumentError):
    pass


class InvalidInstrumentAddressError(InstrumentError, ValueError):
    def __init__(self, address: object, *, field_name: str = "instrument_ip") -> None:
        self.address = address
        self.field_name = field_name
        super().__init__(f"invalid IPv4 address for {field_name}: {address!r}")


class DiscoveryError(InstrumentError):
    pass


class CrcMismatchError(InstrumentProtocolError):
    pass


class InvalidFrameError(InstrumentProtocolError):
    pass


class HeartbeatError(InstrumentError):
    pass

