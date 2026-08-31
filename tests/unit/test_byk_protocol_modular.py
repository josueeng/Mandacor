from __future__ import annotations

from pathlib import Path

from mandacor.infrastructure.instruments.byk.crc import crc16_xmodem_bytes
from mandacor.infrastructure.instruments.byk.framing import BufferedFrameReader, build_request
from mandacor.infrastructure.instruments.byk.protocol import parse_instrument_info


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "byk"


class _OneChunkStream:
    def __init__(self, data):
        self.data = data

    def recv(self, size):
        data, self.data = self.data, b""
        return data


def test_new_crc_matches_real_capture():
    header = (FIXTURES / "frames" / "response_header.bin").read_bytes()
    payload = (FIXTURES / "frames" / "response_payload.bin").read_bytes()
    expected = (FIXTURES / "frames" / "response_crc.bin").read_bytes()
    assert crc16_xmodem_bytes(header + payload) == expected


def test_new_frame_builder_matches_real_get_info_request():
    expected = (FIXTURES / "tcp" / "get_instrument_info_request.bin").read_bytes()
    header, body = build_request(4, "GetInstrumentInfo")
    assert header + body == expected


def test_real_response_stream_parses_ack_and_xml():
    stream = (FIXTURES / "tcp" / "get_instrument_info_response.bin").read_bytes()
    reader = BufferedFrameReader(_OneChunkStream(stream))
    ack = reader.read_message()
    data = reader.read_message()
    assert (ack.kind, ack.command_id) == ("ack", 4)
    assert data.xml == (FIXTURES / "xml" / "get_instrument_info_response.xml").read_bytes()
    assert reader.buffered_bytes == b""


def test_coalesced_messages_remain_buffered_until_consumed():
    response = (FIXTURES / "tcp" / "get_instrument_info_response.bin").read_bytes()
    reader = BufferedFrameReader(_OneChunkStream(response + response))
    first_ack = reader.read_message()
    first_data = reader.read_message()
    assert first_ack.kind == "ack"
    assert first_data.kind == "data"
    assert reader.buffered_bytes == response
    assert reader.read_message().kind == "ack"
    assert reader.read_message().kind == "data"
    assert reader.buffered_bytes == b""


def test_real_instrument_info_parses_with_golden_semantics(golden_module):
    xml = (FIXTURES / "xml" / "get_instrument_info_response.xml").read_bytes()
    info = parse_instrument_info(xml, ip="192.0.2.13")
    _, golden_values = golden_module.parse_values(xml)
    assert info.manufacturer == "BYK"
    assert info.model == golden_values["UnitIdentCode"]
    assert info.serial == golden_values["SerialNumber"]
    assert info.firmware == golden_values["FirmwareVersion"]

