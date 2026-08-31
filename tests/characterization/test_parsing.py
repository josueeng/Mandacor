from __future__ import annotations

import math


def _synthetic_measurement_xml(*, omit: str | None = None) -> bytes:
    """SYNTHETIC_TEST_DATA used only to characterize the frozen parser."""
    scales = []
    for angle in (15, 25, 45, 75, 105):
        for index, coordinate in enumerate(("L", "a", "b"), start=1):
            name = f"{coordinate}* {angle}"
            if name == omit:
                continue
            value = angle + index / 10
            scales.append(f'<ScaleValue Name="{name}" Value="{value}" />')
    return (
        '<CommandResult>'
        '<ParameterString Name="Result" Value="OK" />'
        '<ParameterDouble Name="DeviceTemperature" Value="23.75" />'
        '<MeasureValue Id="151" Name="Synthetic sample" '
        'TimeStamp="2026-08-29T12:00:00" Guid="synthetic-guid">'
        '<DataValueCollection Name="LAB">'
        + "".join(scales)
        + "</DataValueCollection></MeasureValue></CommandResult>"
    ).encode("utf-8")


def test_parse_instrument_info_values(golden_module):
    # SYNTHETIC_TEST_DATA, not a real BYK response.
    xml = (
        b'<CommandResult><Value Name="UnitIdentCode" Value="micro-5-color" />'
        b'<Value Name="SerialNumber" Value="synthetic" /></CommandResult>'
    )
    _, values = golden_module.parse_values(xml)
    assert values == {
        "UnitIdentCode": "micro-5-color",
        "SerialNumber": "synthetic",
    }


def test_parse_measurement_id_list(golden_module, monkeypatch):
    # SYNTHETIC_TEST_DATA, not a real BYK response.
    xml = (
        b'<CommandResult><Guid Id="150" Name="Sample #150" Value="guid-150" />'
        b'<Guid Id="151" Name="Sample #151" Value="guid-151" /></CommandResult>'
    )
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: xml)
    assert golden_module.get_measurement_ids(object()) == [
        {"id": 150, "name": "Sample #150", "guid": "guid-150"},
        {"id": 151, "name": "Sample #151", "guid": "guid-151"},
    ]


def test_synthetic_measurement_characterizes_all_five_angles(golden_module, monkeypatch):
    xml = _synthetic_measurement_xml()
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: xml)
    measurement, error = golden_module.retrieve_measurement(object(), 151)
    assert error is None
    assert measurement["id"] == 151
    assert measurement["guid"] == "synthetic-guid"
    assert measurement["temperature"] == 23.75
    assert set(measurement["angles"]) == {15, 25, 45, 75, 105}
    values = [value for lab in measurement["angles"].values() for value in lab.values()]
    assert len(values) == 15
    assert all(isinstance(value, float) and math.isfinite(value) for value in values)
    assert measurement["angles"][45] == {"L": 45.1, "a": 45.2, "b": 45.3}


def test_incomplete_measurement_currently_uses_none(golden_module, monkeypatch):
    xml = _synthetic_measurement_xml(omit="b* 105")
    monkeypatch.setattr(golden_module, "transact", lambda *args, **kwargs: xml)
    measurement, error = golden_module.retrieve_measurement(object(), 151)
    assert error is None
    assert measurement["angles"][105]["b"] is None

