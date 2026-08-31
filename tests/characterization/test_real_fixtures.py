from __future__ import annotations

import hashlib
import json

import pytest

from conftest import PROJECT_ROOT


FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "byk"


def test_real_capture_files_match_recorded_hashes():
    metadata_path = FIXTURES / "CAPTURE_METADATA.json"
    if not metadata_path.exists():
        pytest.skip("PENDENTE DE CAPTURA REAL: capture metadata")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["evidence"] == "REAL_CAPTURE"
    assert len(metadata["files"]) == 16
    for record in metadata["files"]:
        path = PROJECT_ROOT / record["path"]
        data = path.read_bytes()
        assert len(data) == record["size"]
        assert hashlib.sha256(data).hexdigest() == record["sha256"]


def _parse_real_measurement(golden_module, monkeypatch):
    xml_path = FIXTURES / "xml" / "measurement_response.xml"
    expected_path = FIXTURES / "measurements" / "measurement_real.json"
    if not xml_path.exists() or not expected_path.exists():
        pytest.skip("PENDENTE DE CAPTURA REAL: measurement XML/expected JSON")
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: xml_path.read_bytes())
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected["angles"] = {int(angle): lab for angle, lab in expected["angles"].items()}
    measurement, error = golden_module.retrieve_measurement(object(), expected["id"])
    assert error is None
    assert measurement == expected
    return measurement


def test_real_bykinstrument_capture_when_available():
    path = FIXTURES / "discovery" / "BYKINSTRUMENT.bin"
    if not path.exists():
        pytest.skip("PENDENTE DE CAPTURA REAL: BYKINSTRUMENT.bin")
    assert path.read_bytes().startswith(b"BYKINSTRUMENT")


def test_real_frame_crc_when_available(golden_module):
    header_path = FIXTURES / "frames" / "response_header.bin"
    payload_path = FIXTURES / "frames" / "response_payload.bin"
    crc_path = FIXTURES / "frames" / "response_crc.bin"
    if not all(path.exists() for path in (header_path, payload_path, crc_path)):
        pytest.skip("PENDENTE DE CAPTURA REAL: header/payload/CRC")
    assert golden_module.crc16(header_path.read_bytes() + payload_path.read_bytes()) == crc_path.read_bytes()


def test_real_measurement_xml_when_available(golden_module, monkeypatch):
    _parse_real_measurement(golden_module, monkeypatch)


def test_parse_real_instrument_info(golden_module):
    path = FIXTURES / "xml" / "get_instrument_info_response.xml"
    if not path.exists():
        pytest.skip("PENDENTE DE CAPTURA REAL: instrument info XML")
    _, values = golden_module.parse_values(path.read_bytes())
    assert values["UnitIdentCode"] == "MicroTriColor"
    assert values["FirmwareVersion"] == "1.2.0.24448"


def test_parse_real_measurement_id_list(golden_module, monkeypatch):
    path = FIXTURES / "xml" / "measurement_id_list_response.xml"
    if not path.exists():
        pytest.skip("PENDENTE DE CAPTURA REAL: measurement list XML")
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: path.read_bytes())
    measurements = golden_module.get_measurement_ids(object())
    assert len(measurements) == 3
    assert max(item["id"] for item in measurements) == 3


def test_real_measurement_has_five_angles(golden_module, monkeypatch):
    measurement = _parse_real_measurement(golden_module, monkeypatch)
    assert set(measurement["angles"]) == {15, 25, 45, 75, 105}


def test_real_measurement_has_15_lab_values(golden_module, monkeypatch):
    measurement = _parse_real_measurement(golden_module, monkeypatch)
    values = [value for lab in measurement["angles"].values() for value in lab.values()]
    assert len(values) == 15
    assert all(isinstance(value, float) for value in values)


def test_known_real_measurement_values_are_preserved(golden_module, monkeypatch):
    measurement = _parse_real_measurement(golden_module, monkeypatch)
    assert measurement["id"] == 3
    assert measurement["guid"] == "79bcbeb4-48e5-48cb-9162-6b3a0c26fca9"
    assert measurement["angles"][15] == {
        "L": 77.1218414,
        "a": -0.81717968,
        "b": 1.26897097,
    }
    assert measurement["angles"][105] == {
        "L": 13.9409418,
        "a": -0.318706036,
        "b": -2.96062827,
    }
