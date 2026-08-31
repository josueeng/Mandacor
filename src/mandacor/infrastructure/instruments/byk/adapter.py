from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

from mandacor.config import ConnectionMode, InstrumentConnectionConfig
from mandacor.domain.instruments import DiscoveredInstrument, InstrumentInfo
from mandacor.domain.measurements import (
    Measurement,
    MeasurementError,
    MeasurementNotFoundError,
    MeasurementReference,
)
from mandacor.infrastructure.instruments.byk.client import BykClient
from mandacor.infrastructure.instruments.byk.discovery import BykDiscovery
from mandacor.infrastructure.instruments.byk.exceptions import (
    InstrumentNotFoundError,
    MultipleInstrumentsFoundError,
)
from mandacor.infrastructure.instruments.byk.heartbeat import BykHeartbeat
from mandacor.infrastructure.instruments.byk.measurement_mapper import (
    map_measurement,
    map_measurement_reference,
)
from mandacor.infrastructure.instruments.byk.measurement_parser import MeasurementParseError


logger = logging.getLogger(__name__)


class AdapterState(str, Enum):
    DISCONNECTED = "disconnected"
    DISCOVERING = "discovering"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"


class BykInstrumentAdapter:
    def __init__(
        self,
        config: InstrumentConnectionConfig,
        *,
        discovery_factory: Callable[[InstrumentConnectionConfig], BykDiscovery] = BykDiscovery,
        client_factory: Callable[[InstrumentConnectionConfig], BykClient] = BykClient,
        heartbeat_factory: Callable[..., BykHeartbeat] = BykHeartbeat,
    ) -> None:
        self.config = config
        self._discovery_factory = discovery_factory
        self._client = client_factory(config)
        self._heartbeat_factory = heartbeat_factory
        self._discovery: BykDiscovery | None = None
        self._heartbeat: BykHeartbeat | None = None
        self._state = AdapterState.DISCONNECTED
        self.connected_instrument: DiscoveredInstrument | None = None

    @property
    def state(self) -> AdapterState:
        return self._state

    @property
    def heartbeat_running(self) -> bool:
        return self._heartbeat is not None and self._heartbeat.is_running

    def discover(self) -> list[DiscoveredInstrument]:
        if self.is_connected():
            raise RuntimeError("cannot discover while connected")
        self._state = AdapterState.DISCOVERING
        if self._discovery is not None:
            self._discovery.close()
        self._discovery = self._discovery_factory(self.config)
        try:
            return self._discovery.discover()
        finally:
            self._state = AdapterState.DISCONNECTED

    def _fallback_instrument(self) -> DiscoveredInstrument | None:
        ip = self.config.instrument_ip or self.config.last_known_instrument_ip
        if ip is None:
            return None
        logger.warning("using configured BYK IP fallback", extra={"instrument_ip": ip})
        return DiscoveredInstrument(
            manufacturer="BYK",
            ip=ip,
            tcp_port=self.config.tcp_port,
            udp_port=self.config.udp_port,
            source="manual/fallback configuration",
        )

    def connect(self, instrument: DiscoveredInstrument | None = None) -> None:
        if self.is_connected():
            return
        selected = instrument
        if selected is None and self.config.mode is ConnectionMode.AUTO:
            candidates = self.discover()
            if len(candidates) > 1:
                raise MultipleInstrumentsFoundError(
                    f"{len(candidates)} BYK instruments discovered; explicit selection required"
                )
            selected = candidates[0] if candidates else self._fallback_instrument()
        elif selected is None:
            selected = self._fallback_instrument()
        if selected is None:
            raise InstrumentNotFoundError("no BYK instrument discovered or configured")

        self._state = AdapterState.CONNECTING
        try:
            if self._discovery is not None and self._discovery.channels:
                channels = self._discovery.take_channels()
            else:
                heartbeat_discovery = self._discovery_factory(self.config)
                channels = heartbeat_discovery.open_channels(fallback_destination=selected.ip)
            self._heartbeat = self._heartbeat_factory(
                channels, interval=self.config.heartbeat_interval
            )
            self._heartbeat.start()
            self._client.connect(selected.ip, selected.tcp_port)
            self.connected_instrument = selected
            self._state = AdapterState.CONNECTED
        except BaseException:
            self.disconnect()
            raise

    def disconnect(self) -> None:
        self._state = AdapterState.DISCONNECTING
        self._client.disconnect()
        heartbeat, self._heartbeat = self._heartbeat, None
        if heartbeat is not None:
            heartbeat.stop()
        discovery, self._discovery = self._discovery, None
        if discovery is not None:
            discovery.close()
        self.connected_instrument = None
        self._state = AdapterState.DISCONNECTED

    def get_info(self) -> InstrumentInfo:
        if not self.is_connected():
            raise InstrumentNotFoundError("BYK instrument is not connected")
        return self._client.get_info()

    def is_connected(self) -> bool:
        return self._state is AdapterState.CONNECTED and self._client.is_connected()

    def list_measurements(self) -> list[MeasurementReference]:
        if not self.is_connected():
            raise InstrumentNotFoundError("BYK instrument is not connected")
        references = [
            map_measurement_reference(raw) for raw in self._client.list_raw_measurements()
        ]
        duplicate_ids = {
            reference.measurement_id
            for reference in references
            if sum(item.measurement_id == reference.measurement_id for item in references) > 1
        }
        if duplicate_ids:
            logger.warning(
                "duplicate BYK measurement references preserved",
                extra={"measurement_ids": sorted(duplicate_ids)},
            )
        return sorted(references, key=lambda reference: reference.measurement_id)

    def get_measurement(self, measurement_id: int) -> Measurement:
        if not self.is_connected():
            raise InstrumentNotFoundError("BYK instrument is not connected")
        return map_measurement(self._client.get_raw_measurement(measurement_id))

    def get_latest_reference(self) -> MeasurementReference:
        references = self.list_measurements()
        if not references:
            raise MeasurementNotFoundError("instrument has no stored measurements")
        return max(references, key=lambda reference: reference.measurement_id)

    def get_latest_measurement(self) -> Measurement:
        references = self.list_measurements()
        if not references:
            raise MeasurementNotFoundError("instrument has no stored measurements")
        attempted: set[int] = set()
        failures: list[str] = []
        for reference in sorted(
            references, key=lambda item: item.measurement_id, reverse=True
        ):
            if reference.measurement_id in attempted:
                continue
            attempted.add(reference.measurement_id)
            try:
                return self.get_measurement(reference.measurement_id)
            except (MeasurementError, MeasurementParseError) as error:
                failures.append(f"{reference.measurement_id}: {error}")
                logger.warning(
                    "invalid BYK measurement skipped while finding latest valid",
                    extra={"measurement_id": reference.measurement_id},
                )
        raise MeasurementNotFoundError(
            "no valid stored measurement found" + (f" ({'; '.join(failures)})" if failures else "")
        )

    def __enter__(self) -> "BykInstrumentAdapter":
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
