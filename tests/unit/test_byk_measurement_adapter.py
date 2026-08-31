from __future__ import annotations

from types import MappingProxyType

import pytest

from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle, MeasurementNotFoundError
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter
from mandacor.infrastructure.instruments.byk.measurement_dto import (
    RawBykLabValue,
    RawBykMeasurement,
    RawBykMeasurementReference,
)


def _raw_measurement(measurement_id: int, *, complete: bool = True):
    angles = {
        angle: RawBykLabValue(str(angle + 0.1), str(angle + 0.2), str(angle + 0.3))
        for angle in (15, 25, 45, 75, 105)
        if complete or angle != 105
    }
    return RawBykMeasurement(
        measurement_id=measurement_id,
        guid=f"guid-{measurement_id}",
        timestamp="2026-08-29T12:00:00+00:00",
        name=f"Sample #{measurement_id}",
        instrument_serial="synthetic",
        temperature="20.0",
        angles=MappingProxyType(angles),
    )


class _Channel:
    def close(self):
        pass


class _Discovery:
    def __init__(self, config):
        pass

    @property
    def channels(self):
        return ()

    def open_channels(self, fallback_destination=None):
        return [_Channel()]

    def close(self):
        pass


class _Heartbeat:
    def __init__(self, channels, interval):
        self.is_running = False

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False


class _MeasurementClient:
    references = []
    measurements = {}
    instance = None

    def __init__(self, config):
        self.connected = False
        self.connect_calls = 0
        self.retrieve_calls = []
        self.__class__.instance = self

    def connect(self, ip, port):
        self.connect_calls += 1
        self.connected = True

    def disconnect(self):
        self.connected = False

    def is_connected(self):
        return self.connected

    def list_raw_measurements(self):
        return list(self.references)

    def get_raw_measurement(self, measurement_id):
        self.retrieve_calls.append(measurement_id)
        if measurement_id not in self.measurements:
            raise MeasurementNotFoundError(str(measurement_id))
        return self.measurements[measurement_id]


def _adapter():
    adapter = BykInstrumentAdapter(
        InstrumentConnectionConfig(
            mode=ConnectionMode.MANUAL,
            instrument_ip="192.0.2.13",
        ),
        discovery_factory=_Discovery,
        client_factory=_MeasurementClient,
        heartbeat_factory=_Heartbeat,
    )
    adapter.connect()
    return adapter


def test_list_preserves_duplicates_but_orders_by_id():
    _MeasurementClient.references = [
        RawBykMeasurementReference(3, "g3", "three"),
        RawBykMeasurementReference(1, "g1", "one"),
        RawBykMeasurementReference(3, "g3-duplicate", "duplicate"),
    ]
    adapter = _adapter()
    try:
        assert [item.measurement_id for item in adapter.list_measurements()] == [1, 3, 3]
    finally:
        adapter.disconnect()


def test_latest_reference_and_latest_valid_are_distinct():
    _MeasurementClient.references = [
        RawBykMeasurementReference(2, "g2", "valid"),
        RawBykMeasurementReference(3, "g3", "incomplete"),
    ]
    _MeasurementClient.measurements = {2: _raw_measurement(2), 3: _raw_measurement(3, complete=False)}
    adapter = _adapter()
    try:
        assert adapter.get_latest_reference().measurement_id == 3
        latest = adapter.get_latest_measurement()
        assert latest.measurement_id == 2
        assert _MeasurementClient.instance.retrieve_calls == [3, 2]
    finally:
        adapter.disconnect()


def test_empty_list_has_no_latest_measurement():
    _MeasurementClient.references = []
    _MeasurementClient.measurements = {}
    adapter = _adapter()
    try:
        assert adapter.list_measurements() == []
        with pytest.raises(MeasurementNotFoundError):
            adapter.get_latest_measurement()
    finally:
        adapter.disconnect()


def test_list_and_multiple_gets_reuse_one_connection():
    _MeasurementClient.references = [
        RawBykMeasurementReference(1, "g1", "one"),
        RawBykMeasurementReference(2, "g2", "two"),
    ]
    _MeasurementClient.measurements = {1: _raw_measurement(1), 2: _raw_measurement(2)}
    adapter = _adapter()
    try:
        adapter.list_measurements()
        assert adapter.get_measurement(1).angles[MeasurementAngle.DEG_15].L == 15.1
        assert adapter.get_measurement(2).measurement_id == 2
        assert _MeasurementClient.instance.connect_calls == 1
    finally:
        adapter.disconnect()

