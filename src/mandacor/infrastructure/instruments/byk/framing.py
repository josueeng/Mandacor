from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Protocol

from mandacor.infrastructure.instruments.byk.constants import (
    BYK_MAGIC,
    COMMAND_RESULT_END,
    CRC_SIZE,
    HEADER_SIZE,
)
from mandacor.infrastructure.instruments.byk.crc import crc16_xmodem_bytes
from mandacor.infrastructure.instruments.byk.exceptions import CrcMismatchError, InvalidFrameError


logger = logging.getLogger(__name__)


class Receivable(Protocol):
    def recv(self, size: int) -> bytes: ...


@dataclass(frozen=True, slots=True)
class BykMessage:
    kind: str
    command_id: int
    xml: bytes | None


def make_header(command_id: int) -> bytes:
    return (
        BYK_MAGIC
        + struct.pack("<I", 0)
        + struct.pack("<I", 1)
        + struct.pack("<I", 11)
        + struct.pack("<I", 0)
        + struct.pack("<I", command_id)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0xFFFFFFFF)
    )


def build_request(
    command_id: int,
    name: str,
    parameters: str | None = None,
) -> tuple[bytes, bytes]:
    """Build the exact request parts characterized in the golden reference."""
    header = make_header(command_id)
    if parameters is None:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Command Id="{command_id}" Name="{name}" DestinationId="11" />'
        ).encode("utf-8")
    else:
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Command Id="{command_id}" Name="{name}" DestinationId="11">\r\n'
            '  <Parameters>\r\n'
            f'{parameters}'
            '  </Parameters>\r\n'
            '</Command>'
        ).encode("utf-8")
    return header, xml + crc16_xmodem_bytes(header + xml)


def validate_crc(header: bytes, payload: bytes, received_crc: bytes) -> None:
    expected = crc16_xmodem_bytes(header + payload)
    if received_crc != expected:
        raise CrcMismatchError(
            f"CRC mismatch: received={received_crc.hex()} expected={expected.hex()}"
        )


class BufferedFrameReader:
    """Read one BYK message while retaining coalesced bytes for the next call."""

    def __init__(self, stream: Receivable, *, receive_size: int = 4096) -> None:
        self._stream = stream
        self._receive_size = receive_size
        self._buffer = bytearray()

    @property
    def buffered_bytes(self) -> bytes:
        return bytes(self._buffer)

    def _fill(self, required_size: int | None = None) -> None:
        while required_size is None or len(self._buffer) < required_size:
            chunk = self._stream.recv(self._receive_size)
            if not chunk:
                raise InvalidFrameError("TCP connection closed during BYK frame")
            self._buffer.extend(chunk)
            if required_size is None:
                return

    def _consume(self, size: int) -> bytes:
        self._fill(size)
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def read_message(self) -> BykMessage:
        header = self._consume(HEADER_SIZE)
        if header[:4] != BYK_MAGIC:
            raise InvalidFrameError(f"unexpected BYK magic: {header[:8].hex()}")
        flags = struct.unpack_from("<I", header, 4)[0]
        command_id = struct.unpack_from("<I", header, 20)[0]
        if flags & 0x1000:
            received_crc = self._consume(CRC_SIZE)
            validate_crc(header, b"", received_crc)
            return BykMessage("ack", command_id, None)

        while True:
            marker_index = self._buffer.find(COMMAND_RESULT_END)
            if marker_index >= 0:
                xml_size = marker_index + len(COMMAND_RESULT_END)
                self._fill(xml_size + CRC_SIZE)
                xml = self._consume(xml_size)
                received_crc = self._consume(CRC_SIZE)
                validate_crc(header, xml, received_crc)
                return BykMessage("data", command_id, xml)
            self._fill()

