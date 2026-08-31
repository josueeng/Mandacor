from __future__ import annotations

import binascii


def crc16_xmodem(data: bytes) -> int:
    return binascii.crc_hqx(data, 0)


def crc16_xmodem_bytes(data: bytes) -> bytes:
    return crc16_xmodem(data).to_bytes(2, "big")

