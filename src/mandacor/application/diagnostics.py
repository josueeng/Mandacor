from __future__ import annotations

import hashlib
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mandacor import __version__
from mandacor.application.instrument_service import InstrumentService
from mandacor.infrastructure.config.json_config import JsonConfigurationRepository
from mandacor.infrastructure.storage.pending_adjustment_json import (
    JsonPendingAdjustmentRepository,
    RecoveryFileInvalidError,
)


EXPECTED_GOLDEN_SHA256 = "a74672dbde168962bac4d5640d2c0edb2a08fe8e20ad7b01c0062e5a242d15ba"


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    version: str
    configuration: str
    local_addresses: tuple[str, ...]
    byk: str
    byk_reason: str | None
    discovered_instruments: tuple[str, ...]
    recovery: str
    dataset_directory: str
    golden: str


def _local_addresses() -> tuple[str, ...]:
    try:
        values = {
            item[4][0]
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            if item[4][0]
        }
        return tuple(sorted(values))
    except OSError:
        return ()


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def collect_diagnostics(
    *,
    config_path: Path,
    pending_path: Path,
    data_directory: Path,
    project_root: Path,
    service_factory: Callable[[JsonConfigurationRepository], InstrumentService] = InstrumentService,
) -> DiagnosticReport:
    configuration = "PASS"
    service = None
    try:
        repository = JsonConfigurationRepository(config_path)
        repository.load()
        service = service_factory(repository)
    except Exception as error:
        configuration = f"FAIL ({type(error).__name__})"

    byk = "NOT AVAILABLE"
    byk_reason: str | None = "Configuration unavailable"
    discovered: tuple[str, ...] = ()
    if service is not None:
        try:
            found = service.discover_instruments()
            discovered = tuple(
                f"{item.serial or 'SEM-SERIAL'}@{item.ip}" for item in found
            )
            if found:
                byk = "DISCOVERED"
                byk_reason = None
            else:
                byk_reason = "Instrument not discovered; verify power and local network"
        except Exception as error:
            byk_reason = f"{type(error).__name__}: {error}"
        finally:
            service.disconnect()

    try:
        JsonPendingAdjustmentRepository(pending_path).load()
        recovery = "PASS"
    except RecoveryFileInvalidError:
        recovery = "FAIL (RECOVERY_FILE_INVALID)"

    data_target = data_directory if data_directory.exists() else data_directory.parent
    dataset_directory = "PASS" if data_target.exists() and data_target.is_dir() else "FAIL"
    original = _sha256(project_root / "conect_espectro.py")
    golden_copy = _sha256(project_root / "legacy" / "byk_reader_working.py")
    golden = (
        "PASS"
        if original == golden_copy == EXPECTED_GOLDEN_SHA256
        else "FAIL"
    )
    return DiagnosticReport(
        version=__version__,
        configuration=configuration,
        local_addresses=_local_addresses(),
        byk=byk,
        byk_reason=byk_reason,
        discovered_instruments=discovered,
        recovery=recovery,
        dataset_directory=dataset_directory,
        golden=golden,
    )


def format_diagnostics(report: DiagnosticReport) -> str:
    lines = [
        "MANDACOR DOCTOR",
        f"Version: {report.version}",
        f"Configuration: {report.configuration}",
        f"Local interfaces: {', '.join(report.local_addresses) or 'NOT AVAILABLE'}",
        f"BYK: {report.byk}",
    ]
    if report.byk_reason:
        lines.extend(
            [
                f"Reason: {report.byk_reason}",
                "Suggested: verify instrument power, same LAN, PC interface and TCP 6000.",
            ]
        )
    lines.extend(
        [
            f"Instruments: {', '.join(report.discovered_instruments) or 'NONE'}",
            f"Recovery file: {report.recovery}",
            f"Dataset directory: {report.dataset_directory}",
            f"Golden: {report.golden}",
            "Mode: READ ONLY",
        ]
    )
    return "\n".join(lines)
