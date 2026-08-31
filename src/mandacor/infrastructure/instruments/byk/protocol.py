from __future__ import annotations

import xml.etree.ElementTree as ET

from mandacor.domain.instruments import InstrumentInfo
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentProtocolError


def parse_instrument_info(xml_bytes: bytes, *, ip: str) -> InstrumentInfo:
    try:
        root = ET.fromstring(xml_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ET.ParseError) as error:
        raise InstrumentProtocolError("invalid GetInstrumentInfo XML") from error
    values = {
        element.attrib["Name"]: element.attrib["Value"]
        for element in root.findall(".//*[@Name]")
        if "Value" in element.attrib
    }
    return InstrumentInfo(
        manufacturer="BYK",
        model=values.get("UnitIdentCode"),
        serial=values.get("SerialNumber"),
        firmware=values.get("FirmwareVersion"),
        ip=ip,
    )

