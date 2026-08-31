from __future__ import annotations

from pathlib import Path

from mandacor.application.diagnostics import collect_diagnostics, format_diagnostics


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class OfflineDoctorService:
    instances = []

    def __init__(self, repository):
        self.repository = repository
        self.disconnected = False
        self.__class__.instances.append(self)

    def discover_instruments(self):
        raise TimeoutError("BYK discovery timeout")

    def disconnect(self):
        self.disconnected = True


def test_doctor_is_read_only_and_handles_instrument_offline(tmp_path):
    config = tmp_path / "config.json"
    pending = tmp_path / "pending.json"
    data = tmp_path / "data"
    data.mkdir()
    before = tuple(tmp_path.rglob("*"))
    report = collect_diagnostics(
        config_path=config,
        pending_path=pending,
        data_directory=data,
        project_root=PROJECT_ROOT,
        service_factory=OfflineDoctorService,
    )
    after = tuple(tmp_path.rglob("*"))
    assert before == after
    assert report.configuration == "PASS"
    assert report.byk == "NOT AVAILABLE"
    assert "TimeoutError" in report.byk_reason
    assert report.recovery == "PASS"
    assert report.golden == "PASS"
    assert OfflineDoctorService.instances[-1].disconnected is True
    output = format_diagnostics(report)
    assert "MANDACOR DOCTOR" in output
    assert "Mode: READ ONLY" in output
    assert "Traceback" not in output
