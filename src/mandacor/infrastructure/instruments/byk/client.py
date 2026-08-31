from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Any, Callable

from mandacor.config import InstrumentConnectionConfig
from mandacor.domain.instruments import InstrumentInfo
from mandacor.infrastructure.instruments.byk.constants import (
    GET_INSTRUMENT_INFO_COMMAND_ID,
    GET_INSTRUMENT_INFO_COMMAND_NAME,
    HEADER_BODY_DELAY_SECONDS,
    POST_CONNECT_DELAY_SECONDS,
    RETRIEVE_MEASUREMENT_COMMAND_ID,
    RETRIEVE_MEASUREMENT_COMMAND_NAME,
    RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_ID,
    RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_NAME,
)
from mandacor.infrastructure.instruments.byk.exceptions import (
    InstrumentConnectionError,
    InstrumentProtocolError,
    InstrumentTimeoutError,
)
from mandacor.infrastructure.instruments.byk.framing import BufferedFrameReader, build_request
from mandacor.infrastructure.instruments.byk.protocol import parse_instrument_info
from mandacor.infrastructure.instruments.byk.measurement_dto import (
    RawBykMeasurement,
    RawBykMeasurementReference,
)
from mandacor.infrastructure.instruments.byk.measurement_parser import (
    parse_measurement_references,
    parse_raw_measurement,
)


logger = logging.getLogger(__name__)


class BykClient:
    def __init__(
        self,
        config: InstrumentConnectionConfig,
        *,
        connection_factory: Callable[..., Any] = socket.create_connection,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self._connection_factory = connection_factory
        self._sleep = sleeper
        self._socket: Any | None = None
        self._reader: BufferedFrameReader | None = None
        self._ip: str | None = None
        self._transaction_lock = threading.Lock()

    @property
    def ip(self) -> str | None:
        return self._ip

    def connect(self, ip: str, port: int | None = None) -> None:
        self.disconnect()
        tcp_port = self.config.tcp_port if port is None else port
        logger.debug("connecting to BYK", extra={"tcp_target": f"{ip}:{tcp_port}"})
        try:
            connection = self._connection_factory(
                (ip, tcp_port), timeout=self.config.connection_timeout
            )
            connection.settimeout(self.config.connection_timeout)
        except socket.timeout as error:
            raise InstrumentTimeoutError(f"connection timed out for {ip}:{tcp_port}") from error
        except OSError as error:
            raise InstrumentConnectionError(ip, tcp_port) from error
        self._socket = connection
        self._reader = BufferedFrameReader(connection)
        self._ip = ip
        self._sleep(POST_CONNECT_DELAY_SECONDS)
        logger.info("connected to BYK", extra={"instrument_ip": ip, "tcp_port": tcp_port})

    def disconnect(self) -> None:
        connection, self._socket = self._socket, None
        self._reader = None
        self._ip = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
            logger.info("disconnected from BYK")

    def is_connected(self) -> bool:
        return self._socket is not None and self._reader is not None

    def transact(self, command_id: int, name: str, parameters: str | None = None) -> bytes:
        if self._socket is None or self._reader is None:
            raise InstrumentConnectionError(self._ip or "<disconnected>", self.config.tcp_port)
        header, body = build_request(command_id, name, parameters)
        logger.debug(
            "BYK command",
            extra={
                "command_id": command_id,
                "command_name": name,
                "header_length": len(header),
                "body_length": len(body),
                "crc": body[-2:].hex(),
            },
        )
        with self._transaction_lock:
            try:
                self._socket.sendall(header)
                self._sleep(HEADER_BODY_DELAY_SECONDS)
                self._socket.sendall(body)
                for _ in range(4):
                    message = self._reader.read_message()
                    logger.debug(
                        "BYK response",
                        extra={"response_type": message.kind, "command_id": message.command_id},
                    )
                    if message.kind == "data" and message.xml is not None:
                        return message.xml
            except socket.timeout as error:
                raise InstrumentTimeoutError(f"command {name} timed out") from error
            except OSError as error:
                raise InstrumentConnectionError(self._ip or "<unknown>", self.config.tcp_port) from error
        raise InstrumentProtocolError(f"no XML response received for command {name}")

    def get_info(self) -> InstrumentInfo:
        if self._ip is None:
            raise InstrumentConnectionError("<disconnected>", self.config.tcp_port)
        xml = self.transact(GET_INSTRUMENT_INFO_COMMAND_ID, GET_INSTRUMENT_INFO_COMMAND_NAME)
        return parse_instrument_info(xml, ip=self._ip)

    def list_raw_measurements(self) -> list[RawBykMeasurementReference]:
        xml = self.transact(
            RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_ID,
            RETRIEVE_MEASUREMENT_ID_LIST_COMMAND_NAME,
        )
        return parse_measurement_references(xml)

    def get_raw_measurement(self, measurement_id: int) -> RawBykMeasurement:
        parameters = (
            '    <ParameterInt32 Name="JobListRecordId" '
            f'Value="{measurement_id}" />\r\n'
        )
        xml = self.transact(
            RETRIEVE_MEASUREMENT_COMMAND_ID,
            RETRIEVE_MEASUREMENT_COMMAND_NAME,
            parameters,
        )
        return parse_raw_measurement(xml, requested_id=measurement_id)

    def __enter__(self) -> "BykClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()
