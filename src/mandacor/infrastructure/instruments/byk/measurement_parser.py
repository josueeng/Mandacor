from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from types import MappingProxyType

from mandacor.domain.measurements import MeasurementError, MeasurementNotFoundError
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentProtocolError
from mandacor.infrastructure.instruments.byk.measurement_dto import (
    RawBykLabValue,
    RawBykMeasurement,
    RawBykMeasurementReference,
)


class MeasurementParseError(InstrumentProtocolError, MeasurementError):
    pass


_LAB_NAME = re.compile(r"^(L|a|b)\*\s+(\d+)$")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _root(xml_bytes: bytes) -> ET.Element:
    try:
        return ET.fromstring(xml_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ET.ParseError) as error:
        raise MeasurementParseError("invalid BYK measurement XML") from error


def parse_measurement_references(xml_bytes: bytes) -> list[RawBykMeasurementReference]:
    root = _root(xml_bytes)
    references: list[RawBykMeasurementReference] = []
    for element in root.iter():
        if _local_name(element.tag) != "Guid":
            continue
        try:
            measurement_id = int(element.attrib["Id"])
        except (KeyError, TypeError, ValueError) as error:
            raise MeasurementParseError("measurement reference has invalid or missing Id") from error
        references.append(
            RawBykMeasurementReference(
                measurement_id=measurement_id,
                name=element.attrib.get("Name"),
                guid=element.attrib.get("Value"),
            )
        )
    return references


def parse_raw_measurement(xml_bytes: bytes, *, requested_id: int) -> RawBykMeasurement:
    root = _root(xml_bytes)
    for element in root.iter():
        if element.attrib.get("Name") == "Result" and element.attrib.get("Value") != "OK":
            description = element.attrib.get("Description", "BYK returned a non-OK result")
            raise MeasurementNotFoundError(
                f"measurement {requested_id} was not retrieved: {description}"
            )
    measure = next(
        (element for element in root.iter() if _local_name(element.tag) == "MeasureValue"),
        None,
    )
    if measure is None:
        raise MeasurementNotFoundError(f"measurement {requested_id} response has no MeasureValue")
    try:
        measurement_id = int(measure.attrib["Id"])
    except (KeyError, TypeError, ValueError) as error:
        raise MeasurementParseError("MeasureValue has invalid or missing Id") from error
    if measurement_id != requested_id:
        raise MeasurementParseError(
            f"requested measurement {requested_id}, response contains {measurement_id}"
        )

    values: dict[int, dict[str, str | None]] = {}
    temperature: str | None = None
    for element in measure.iter():
        name = element.attrib.get("Name")
        if name == "DeviceTemperature":
            temperature = element.attrib.get("Value")
        if _local_name(element.tag) != "ScaleValue" or name is None:
            continue
        match = _LAB_NAME.fullmatch(name)
        if match is None:
            continue
        coordinate, angle_text = match.groups()
        values.setdefault(int(angle_text), {})[coordinate] = element.attrib.get("Value")

    angles = {
        angle: RawBykLabValue(
            L=coordinates.get("L"),
            a=coordinates.get("a"),
            b=coordinates.get("b"),
        )
        for angle, coordinates in values.items()
    }
    return RawBykMeasurement(
        measurement_id=measurement_id,
        guid=measure.attrib.get("Guid"),
        timestamp=measure.attrib.get("TimeStamp"),
        name=measure.attrib.get("Name"),
        instrument_serial=measure.attrib.get("SerialNumber"),
        temperature=temperature,
        angles=MappingProxyType(angles),
    )
