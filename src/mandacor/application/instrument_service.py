from __future__ import annotations

from dataclasses import replace
import threading
from typing import Callable

from mandacor.config import ConnectionMode, InstrumentConnectionConfig, validate_ipv4_address
from mandacor.domain.instruments import DiscoveredInstrument, InstrumentInfo
from mandacor.domain.measurements import Measurement, MeasurementReference
from mandacor.infrastructure.instruments.byk.adapter import BykInstrumentAdapter
from mandacor.application.measurement_wait import (
    MeasurementSnapshot,
    MeasurementWaitService,
)
from mandacor.ports.configuration import ConfigurationRepository
from mandacor.ports.instrument import InstrumentAdapter


class InstrumentService:
    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
        *,
        adapter_factory: Callable[[InstrumentConnectionConfig], InstrumentAdapter] = BykInstrumentAdapter,
    ) -> None:
        self._repository = configuration_repository
        self._adapter_factory = adapter_factory
        self._config = self._repository.load()
        self._adapter: InstrumentAdapter | None = None
        self._instrument_info: InstrumentInfo | None = None
        self._measurement_wait_service: MeasurementWaitService | None = None

    @property
    def config(self) -> InstrumentConnectionConfig:
        return self._config

    def configure(self, config: InstrumentConnectionConfig) -> None:
        self.disconnect()
        self._repository.save(config)
        self._config = config

    def _new_adapter(self, config: InstrumentConnectionConfig) -> InstrumentAdapter:
        self.disconnect()
        self._adapter = self._adapter_factory(config)
        return self._adapter

    def _set_connected_instrument(
        self, adapter: InstrumentAdapter, info: InstrumentInfo
    ) -> None:
        self._instrument_info = info
        self._measurement_wait_service = MeasurementWaitService(adapter, info)

    def discover_instruments(self) -> list[DiscoveredInstrument]:
        config = replace(self._config, mode=ConnectionMode.AUTO)
        return self._new_adapter(config).discover()

    def connect_auto(self) -> InstrumentInfo:
        config = replace(self._config, mode=ConnectionMode.AUTO)
        adapter = self._new_adapter(config)
        adapter.connect()
        info = adapter.get_info()
        self._set_connected_instrument(adapter, info)
        self._config = replace(config, last_known_instrument_ip=info.ip)
        self._repository.save(self._config)
        return info

    def connect_manual(self, ip: str) -> InstrumentInfo:
        validated_ip = validate_ipv4_address(ip, field_name="instrument_ip")
        config = replace(
            self._config,
            mode=ConnectionMode.MANUAL,
            instrument_ip=validated_ip,
        )
        adapter = self._new_adapter(config)
        adapter.connect()
        info = adapter.get_info()
        self._set_connected_instrument(adapter, info)
        self._config = replace(config, last_known_instrument_ip=info.ip)
        self._repository.save(self._config)
        return info

    def disconnect(self) -> None:
        adapter, self._adapter = self._adapter, None
        self._instrument_info = None
        self._measurement_wait_service = None
        if adapter is not None:
            adapter.disconnect()

    def get_status(self) -> str:
        if self._adapter is not None and self._adapter.is_connected():
            return "CONNECTED"
        return "DISCONNECTED"

    def _connected_adapter(self) -> InstrumentAdapter:
        if self._adapter is None or not self._adapter.is_connected():
            raise RuntimeError("instrument is not connected")
        return self._adapter

    def list_measurements(self) -> list[MeasurementReference]:
        return self._connected_adapter().list_measurements()

    def get_measurement(self, measurement_id: int) -> Measurement:
        return self._connected_adapter().get_measurement(measurement_id)

    def get_latest_reference(self) -> MeasurementReference:
        return self._connected_adapter().get_latest_reference()

    def get_latest_measurement(self) -> Measurement:
        return self._connected_adapter().get_latest_measurement()

    def _wait_service(self) -> MeasurementWaitService:
        self._connected_adapter()
        if self._measurement_wait_service is None:
            raise RuntimeError("measurement wait service is unavailable")
        return self._measurement_wait_service

    def create_measurement_snapshot(self) -> MeasurementSnapshot:
        return self._wait_service().create_snapshot()

    def wait_for_new_measurement(
        self,
        snapshot: MeasurementSnapshot,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
        cancellation: threading.Event | None = None,
    ) -> Measurement:
        return self._wait_service().wait_for_new_measurement(
            snapshot,
            timeout=(
                self._config.measurement_wait_timeout if timeout is None else timeout
            ),
            poll_interval=(
                self._config.measurement_poll_interval
                if poll_interval is None
                else poll_interval
            ),
            cancellation=cancellation,
            max_transient_poll_errors=self._config.max_transient_poll_errors,
            candidate_stabilization_retries=(
                self._config.candidate_stabilization_retries
            ),
            candidate_stabilization_interval=(
                self._config.candidate_stabilization_interval
            ),
        )
