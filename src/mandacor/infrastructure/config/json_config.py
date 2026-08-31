from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from mandacor.config import (
    DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS,
    DEFAULT_CANDIDATE_STABILIZATION_RETRIES,
    DEFAULT_MAX_TRANSIENT_POLL_ERRORS,
    DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS,
    DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS,
    ConnectionMode,
    InstrumentConnectionConfig,
)


SCHEMA_VERSION = 1


class JsonConfigurationRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> InstrumentConnectionConfig:
        if not self.path.exists():
            return InstrumentConnectionConfig()
        document = json.loads(self.path.read_text(encoding="utf-8"))
        if document.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported configuration schema: {document.get('schema_version')!r}")
        connection = document["instrument"]["connection"]
        return InstrumentConnectionConfig(
            mode=ConnectionMode(connection["mode"]),
            instrument_ip=connection.get("instrument_ip"),
            last_known_instrument_ip=connection.get("last_known_instrument_ip"),
            discovery_address=connection.get("discovery_address"),
            local_interface=connection.get("local_interface"),
            tcp_port=connection["tcp_port"],
            udp_port=connection["udp_port"],
            discovery_timeout=connection["discovery_timeout"],
            connection_timeout=connection["connection_timeout"],
            heartbeat_interval=connection["heartbeat_interval"],
            measurement_wait_timeout=connection.get(
                "measurement_wait_timeout", DEFAULT_MEASUREMENT_WAIT_TIMEOUT_SECONDS
            ),
            measurement_poll_interval=connection.get(
                "measurement_poll_interval", DEFAULT_MEASUREMENT_POLL_INTERVAL_SECONDS
            ),
            max_transient_poll_errors=connection.get(
                "max_transient_poll_errors", DEFAULT_MAX_TRANSIENT_POLL_ERRORS
            ),
            candidate_stabilization_retries=connection.get(
                "candidate_stabilization_retries",
                DEFAULT_CANDIDATE_STABILIZATION_RETRIES,
            ),
            candidate_stabilization_interval=connection.get(
                "candidate_stabilization_interval",
                DEFAULT_CANDIDATE_STABILIZATION_INTERVAL_SECONDS,
            ),
        )

    def save(self, config: InstrumentConnectionConfig) -> None:
        connection = asdict(config)
        connection["mode"] = config.mode.value
        document = {
            "schema_version": SCHEMA_VERSION,
            "instrument": {
                "manufacturer": "BYK",
                "connection": connection,
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
