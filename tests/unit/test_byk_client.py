from __future__ import annotations

import socket

import pytest

from mandacor.config import InstrumentConnectionConfig
from mandacor.infrastructure.instruments.byk.client import BykClient
from mandacor.infrastructure.instruments.byk.exceptions import (
    InstrumentConnectionError,
    InstrumentTimeoutError,
)


def test_valid_unavailable_address_has_controlled_timeout():
    def timeout_factory(*args, **kwargs):
        raise socket.timeout("simulated timeout")

    client = BykClient(
        InstrumentConnectionConfig(connection_timeout=0.01),
        connection_factory=timeout_factory,
        sleeper=lambda _: None,
    )
    with pytest.raises(InstrumentTimeoutError):
        client.connect("192.0.2.50")
    assert not client.is_connected()


def test_connection_refusal_preserves_target_context():
    def refused_factory(*args, **kwargs):
        raise ConnectionRefusedError("simulated refusal")

    client = BykClient(
        InstrumentConnectionConfig(),
        connection_factory=refused_factory,
        sleeper=lambda _: None,
    )
    with pytest.raises(InstrumentConnectionError) as captured:
        client.connect("198.51.100.50", 6100)
    assert captured.value.address == "198.51.100.50"
    assert captured.value.port == 6100
    assert not client.is_connected()

