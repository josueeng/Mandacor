from __future__ import annotations

from datetime import timezone
from pathlib import Path

import pytest

from mandacor.domain.measurements import (
    IncompleteMeasurementError,
    InvalidMeasurementValueError,
    MeasurementAngle,
    MeasurementNotFoundError,
)
from mandacor.infrastructure.instruments.byk.constants import (
    RETRIEVE_MEASUREMENT_COMMAND_ID,
    RETRIEVE_MEASUREMENT_COMMAND_NAME,
    RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_ID,
    RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_NAME,
)
from mandacor.infrastructure.instruments.byk.framing import build_request
from mandacor.infrastructure.instruments.byk.measurement_mapper import map_measurement
from mandacor.infrastructure.instruments.byk.measurement_parser import (
    parse_measurement_references,
    parse_raw_measurement,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "byk"
SYNTHETIC = FIXTURES / "synthetic"


def _real_measurement():
    raw = parse_raw_measurement(
        (FIXTURES / "xml" / "measurement_response.xml").read_bytes(), requested_id=3
    )
    return raw, map_measurement(raw)


def test_real_fixture_pipeline_preserves_identity_and_precision():
    raw, measurement = _real_measurement()
    assert raw.angles[15].L == "7.71218414e+01"
    assert measurement.measurement_id == 3
    assert measurement.guid == "79bcbeb4-48e5-48cb-9162-6b3a0c26fca9"
    assert measurement.name == "Sample #3"
    assert measurement.instrument_serial == "1327634"
    assert measurement.timestamp_raw == "2026-08-27T11:29:13+00:00"
    assert measurement.timestamp is not None
    assert measurement.timestamp.tzinfo == timezone.utc
    assert measurement.angles[MeasurementAngle.DEG_15].L == 77.1218414
    assert measurement.angles[MeasurementAngle.DEG_25].a == -0.799715519
    assert measurement.angles[MeasurementAngle.DEG_45].b == -0.0945866108
    assert measurement.angles[MeasurementAngle.DEG_75].L == 17.905941
    assert measurement.angles[MeasurementAngle.DEG_105].b == -2.96062827
    values = [value for lab in measurement.angles.values() for value in (lab.L, lab.a, lab.b)]
    assert len(values) == 15


def test_new_measurement_matches_golden_fixture(golden_module, monkeypatch):
    xml = (FIXTURES / "xml" / "measurement_response.xml").read_bytes()
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: xml)
    golden, error = golden_module.retrieve_measurement(object(), 3)
    assert error is None
    _, measurement = _real_measurement()
    assert golden["id"] == measurement.measurement_id
    assert golden["guid"] == measurement.guid
    assert golden["timestamp"] == measurement.timestamp_raw
    assert golden["name"] == measurement.name
    assert golden["angles"] == {
        int(angle): {"L": lab.L, "a": lab.a, "b": lab.b}
        for angle, lab in measurement.angles.items()
    }


def test_real_measurement_list_is_mapped_without_assuming_xml_order():
    raw = parse_measurement_references(
        (FIXTURES / "xml" / "measurement_id_list_response.xml").read_bytes()
    )
    assert [(item.measurement_id, item.name, item.guid) for item in raw] == [
        (1, "Sample #1", "17849ebb-84a3-4a41-a56e-4188bdcfb4eb"),
        (2, "Sample #2", "24cc5718-bf8f-43d9-bbc0-546de9c1448e"),
        (3, "Sample #3", "79bcbeb4-48e5-48cb-9162-6b3a0c26fca9"),
    ]


def test_measurement_requests_match_real_captures():
    list_header, list_body = build_request(
        RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_ID,
        RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_NAME,
    )
    assert list_header + list_body == (
        FIXTURES / "tcp" / "measurement_id_list_request.bin"
    ).read_bytes()
    parameters = '    <ParameterInt32 Name="JobListRecordId" Value="3" />\r\n'
    get_header, get_body = build_request(
        RETRIEVE_MEASUREMENT_COMMAND_ID,
        RETRIEVE_MEASUREMENT_COMMAND_NAME,
        parameters,
    )
    assert get_header + get_body == (FIXTURES / "tcp" / "measurement_request.bin").read_bytes()


@pytest.mark.parametrize(
    ("filename", "measurement_id", "error_type"),
    [
        ("missing_105.xml", 901, IncompleteMeasurementError),
        ("missing_45_b.xml", 902, IncompleteMeasurementError),
        ("invalid_lab.xml", 903, InvalidMeasurementValueError),
        ("nan_lab.xml", 904, InvalidMeasurementValueError),
    ],
)
def test_synthetic_invalid_measurements_are_rejected(filename, measurement_id, error_type):
    raw = parse_raw_measurement((SYNTHETIC / filename).read_bytes(), requested_id=measurement_id)
    with pytest.raises(error_type):
        map_measurement(raw)


def test_namespaced_measurement_references_are_supported():
    xml = (
        b'<x:CommandResult xmlns:x="urn:test"><x:Guid Id="7" Name="S" '
        b'Value="synthetic-guid" /></x:CommandResult>'
    )
    references = parse_measurement_references(xml)
    assert references[0].measurement_id == 7


def test_duplicate_references_remain_visible_to_the_caller():
    xml = (
        b'<CommandResult><Guid Id="2" Name="first" Value="g1" />'
        b'<Guid Id="2" Name="duplicate" Value="g2" /></CommandResult>'
    )
    references = parse_measurement_references(xml)
    assert [item.name for item in references] == ["first", "duplicate"]


def test_nonexistent_measurement_response_is_explicit_error():
    with pytest.raises(MeasurementNotFoundError, match="999999"):
        parse_raw_measurement(
            (SYNTHETIC / "not_found.xml").read_bytes(), requested_id=999999
        )
