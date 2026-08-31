from __future__ import annotations

import struct


def test_crc_xmodem_matches_canonical_check_vector(golden_module):
    # SYNTHETIC_TEST_DATA: canonical algorithm check, not a captured BYK frame.
    assert golden_module.crc16(b"123456789") == bytes.fromhex("31c3")


def test_bykquery_bytes_are_stable(golden_module):
    # SYNTHETIC_TEST_DATA: fixed local port makes the code behavior deterministic.
    expected = b"BYKQUERY" + (b"\x00" * 10) + b"\x01\x00\x34\x12"
    assert golden_module.build_discovery_query(0x1234) == expected
    assert len(expected) == 22


def test_header_layout_and_command_identifiers_are_stable(golden_module):
    for command_id in (4, 42, 143):
        header = golden_module.make_header(command_id)
        assert len(header) == 32
        assert header[:4] == b"GB\x03\x00"
        assert struct.unpack("<7I", header[4:]) == (
            0,
            1,
            11,
            0,
            command_id,
            0,
            0xFFFFFFFF,
        )


def test_request_crc_covers_header_and_xml(golden_module):
    # SYNTHETIC_TEST_DATA built by the frozen implementation.
    header, body = golden_module.build_request(4, "GetInstrumentInfo")
    xml, received_crc = body[:-2], body[-2:]
    assert received_crc == golden_module.crc16(header + xml)
    assert b'Id="4"' in xml
    assert b'Name="GetInstrumentInfo"' in xml


class _ChunkSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def recv(self, size):
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self.chunks.insert(0, chunk[size:])
        return chunk[:size]


def test_ack_frame_is_recognized_and_crc_checked(golden_module):
    # SYNTHETIC_TEST_DATA: characterizes current framing without claiming capture.
    header = bytearray(golden_module.make_header(4))
    struct.pack_into("<I", header, 4, 0x1000)
    header = bytes(header)
    crc = golden_module.crc16(header)
    message = golden_module.recv_message(_ChunkSocket([header, crc]))
    assert message == {"type": "ack", "command_id": 4, "xml": None}


def test_xml_can_arrive_fragmented(golden_module):
    # SYNTHETIC_TEST_DATA: documents accumulation until literal XML_END.
    header = golden_module.make_header(42)
    xml = b"<CommandResult><Value /></CommandResult>"
    crc = golden_module.crc16(header + xml)
    socket = _ChunkSocket([header, xml[:9], xml[9:31], xml[31:] + crc])
    message = golden_module.recv_message(socket)
    assert message["type"] == "data"
    assert message["xml"] == xml


def test_current_receiver_consumes_coalesced_following_frame(golden_module):
    # KNOWN_DEBT: recv(4096) consumes and then discards bytes after current CRC.
    header = golden_module.make_header(42)
    xml = b"<CommandResult></CommandResult>"
    crc = golden_module.crc16(header + xml)
    following_frame = b"NEXT-FRAME-BYTES"
    socket = _ChunkSocket([header, xml + crc + following_frame])
    message = golden_module.recv_message(socket)
    assert message["xml"] == xml
    assert socket.chunks == []

