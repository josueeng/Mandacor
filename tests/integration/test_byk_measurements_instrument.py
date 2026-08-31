from __future__ import annotations

import pytest

from mandacor.config import InstrumentConnectionConfig
from mandacor.domain.measurements import MeasurementAngle, MeasurementError
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter


@pytest.mark.instrument
def test_real_measurement_session_lists_and_retrieves_all_records():
    adapter = BykInstrumentAdapter(InstrumentConnectionConfig(discovery_timeout=4.0))
    results = {}
    try:
        adapter.connect()
        info = adapter.get_info()
        references = adapter.list_measurements()
        assert info.model == "MicroTriColor"
        assert [reference.measurement_id for reference in references] == sorted(
            reference.measurement_id for reference in references
        )
        assert {1, 2, 3}.issubset({reference.measurement_id for reference in references})
        for reference in references:
            try:
                measurement = adapter.get_measurement(reference.measurement_id)
            except MeasurementError as error:
                results[reference.measurement_id] = f"INVALID: {error}"
            else:
                results[reference.measurement_id] = measurement
        measurement = results[3]
        assert not isinstance(measurement, str)
        assert set(measurement.angles) == set(MeasurementAngle)
        assert measurement.angles[MeasurementAngle.DEG_15].L == 77.1218414
        assert measurement.angles[MeasurementAngle.DEG_105].b == -2.96062827
        assert adapter.heartbeat_running
    finally:
        adapter.disconnect()
    assert not adapter.heartbeat_running
    print({key: "VALID" if not isinstance(value, str) else value for key, value in results.items()})

