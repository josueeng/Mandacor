from __future__ import annotations

import threading
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from mandacor.api.app import create_app
from mandacor.api.service import MandacorApiService
from mandacor.application.measurement_wait import (
    MeasurementIdentity,
    MeasurementSnapshot,
    MeasurementWaitCancelledError,
    NewMeasurementTimeoutError,
)
from mandacor.config import ApiConfig
from mandacor.domain.adjustments import AdjustmentComponent
from mandacor.domain.instruments import DiscoveredInstrument, InstrumentInfo
from mandacor.domain.measurements import (
    LabValue,
    Measurement,
    MeasurementAngle,
    MeasurementNotFoundError,
    MeasurementReference,
)
from mandacor.domain.sessions import ColorSession
from mandacor.domain.pigments import FinishType, PaintContext, PaintSystem
from mandacor.infrastructure.instruments.byk.exceptions import InstrumentError, InstrumentTimeoutError
from mandacor.infrastructure.storage.pending_adjustment_json import JsonPendingAdjustmentRepository
from mandacor.infrastructure.storage.formula_sqlite import SqliteFormulaCatalog


INFO = InstrumentInfo("BYK", "192.168.1.13", "MicroTriColor", "SERIAL-1", "1.0")


def _measurement(measurement_id, *, offset=0.0):
    return Measurement(
        measurement_id,
        {
            angle: LabValue(50 + offset + int(angle) / 100, 1 + offset, -1 + offset)
            for angle in MeasurementAngle
        },
        guid=f"guid-{measurement_id}",
        instrument_serial="SERIAL-1",
    )


class FakeInstrument:
    def __init__(self):
        self.connected = False
        self.connect_calls = []
        self.disconnect_calls = 0
        self.discoveries = [
            DiscoveredInstrument("BYK", "192.168.1.13", 6000, 6002, serial="SERIAL-1")
        ]
        self.measurements = {12: _measurement(12), 13: _measurement(13, offset=0.2)}
        self.wait_outcomes = []
        self.latest_outcomes = []
        self.snapshot_calls = 0
        self.discover_error = None

    def get_status(self):
        return "CONNECTED" if self.connected else "DISCONNECTED"

    def discover_instruments(self):
        if self.discover_error:
            raise self.discover_error
        return list(self.discoveries)

    def connect_manual(self, host):
        if host == "invalid":
            raise ValueError("invalid host")
        self.connect_calls.append(("manual", host))
        self.connected = True
        return INFO

    def connect_auto(self):
        self.connect_calls.append(("auto", None))
        self.connected = True
        return INFO

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False

    def list_measurements(self):
        if not self.connected:
            raise RuntimeError("not connected")
        return [MeasurementReference(key, value.guid) for key, value in sorted(self.measurements.items())]

    def get_measurement(self, measurement_id):
        try:
            return self.measurements[measurement_id]
        except KeyError as error:
            raise MeasurementNotFoundError(f"measurement {measurement_id} not found") from error

    def get_latest_measurement(self):
        if self.latest_outcomes:
            outcome = self.latest_outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        if not self.measurements:
            raise MeasurementNotFoundError("instrument has no stored measurements")
        return self.measurements[max(self.measurements)]

    def create_measurement_snapshot(self):
        self.snapshot_calls += 1
        return MeasurementSnapshot(
            frozenset(
                MeasurementIdentity("SERIAL-1", item.measurement_id, item.guid)
                for item in self.measurements.values()
            ),
            "SERIAL-1",
            datetime.now(timezone.utc),
            uuid.uuid4(),
        )

    def wait_for_new_measurement(self, snapshot, *, cancellation=None, **kwargs):
        if cancellation is not None and cancellation.is_set():
            raise MeasurementWaitCancelledError("cancelled")
        outcome = self.wait_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        self.measurements[outcome.measurement_id] = outcome
        return outcome


@pytest.fixture
def api_bundle():
    instrument = FakeInstrument()
    service = MandacorApiService(instrument)
    app = create_app(service)
    return instrument, service, app


def _connected_client(bundle):
    instrument, service, app = bundle
    instrument.connected = True
    service.connected_info = INFO
    return TestClient(app)


def _ready_session(service):
    session = ColorSession.create("SERIAL-1").with_target(_measurement(12)).with_sample(
        _measurement(13, offset=0.2)
    )
    service.sessions.save(session)
    return session


def _adjustment_payload(*, quantity="0.10"):
    return {
        "system": "POLYESTER_BASECOAT",
        "finish": "METALLIC",
        "volume_ml": "450",
        "components": [{"pigment_code": "BP226", "quantity_g": quantity}],
        "operator_reason": "decisão informada pelo operador",
    }


def test_health_returns_200_and_import_does_not_connect(api_bundle):
    instrument, _, app = api_bundle
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.json() == {
            "status": "ok",
            "service": "mandacor",
            "version": "0.4.0",
            "api_version": "v1",
            "recovery": "OK",
            "recovery_error": None,
        }
        assert uuid.UUID(health.headers["X-Request-ID"])
        assert client.get("/api/v1/health").status_code == 200
        assert instrument.connect_calls == []


def test_formula_catalog_search_and_detail(api_bundle):
    with TestClient(api_bundle[2]) as client:
        search = client.get(
            "/api/v1/formulas",
            params={"q": "vermelho fogo scania", "system": "POLIESTER"},
        )
        assert search.status_code == 200
        payload = search.json()
        assert payload["total"] >= 1
        assert any(item["code"] == "210009850101" for item in payload["items"])
        assert any(item["display_code"] == "210-00985" for item in payload["items"])

        commercial = client.get(
            "/api/v1/formulas",
            params={"q": "610-03121", "manufacturer": "FIAT", "year": "1995"},
        )
        assert commercial.status_code == 200
        assert any(item["code"] == "610031210119" for item in commercial.json()["items"])

        detail = client.get("/api/v1/formulas/210009850101")
        assert detail.status_code == 200
        formula = detail.json()
        assert formula["description"] == "VERMELHO FOGO LISA"
        assert formula["display_code"] == "210-00985"
        assert formula["variants"][0]["total_weight_g"] == "872.3"
        assert formula["variants"][0]["components"][-1]["weight_g"] == "296.6"


def test_formula_catalog_rejects_unknown_system_and_missing_code(api_bundle):
    with TestClient(api_bundle[2]) as client:
        invalid = client.get("/api/v1/formulas", params={"system": "INVALIDO"})
        assert invalid.status_code == 400
        assert invalid.json()["error"]["code"] == "INVALID_REQUEST"

        missing = client.get("/api/v1/formulas/INEXISTENTE")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "FORMULA_NOT_FOUND"


def test_formula_catalog_does_not_merge_obsolete_skymix_revision(api_bundle):
    with TestClient(api_bundle[2]) as client:
        response = client.get("/api/v1/formulas/210023200101")
        assert response.status_code == 200
        variant = response.json()["variants"][0]
        assert variant["updated_at"] == "2010-04-01T00:00"
        assert variant["total_weight_g"] == "903.9"
        assert [(item["base_code"], item["weight_g"]) for item in variant["components"]] == [
            ("BP218", "3.3"),
            ("BP216", "11.5"),
            ("BP299", "54.2"),
            ("TH700", "307.3"),
            ("BP240", "527.6"),
        ]


def test_formula_crud_and_measurement_dataset_api(api_bundle, tmp_path):
    source = Path(__file__).resolve().parents[2] / "data" / "formulas.sqlite3"
    editable_path = tmp_path / "formulas.sqlite3"
    shutil.copy2(source, editable_path)
    instrument, service, _ = api_bundle
    session = _ready_session(service)
    app = create_app(service, formula_catalog=SqliteFormulaCatalog(editable_path))
    payload = {
        "code": "210-99998", "description": "TESTE API METALICO", "year": "2026",
        "universal_code": "API", "nuance": "A", "manufacturer": "MANDACOR",
        "observations": "", "system": "POLIESTER", "finish_label": "METALICO",
        "variants": [{
            "condition": "DILUIDO", "package": "1 Quarto", "version": 1,
            "components": [{"base_code": "BP240", "base_name": "Branco", "weight_g": "903.9"}],
        }],
    }
    with TestClient(app) as client:
        created = client.post("/api/v1/formulas", json=payload)
        assert created.status_code == 201
        code = created.json()["code"]
        assert created.json()["origin"] == "USER"

        payload["description"] = "TESTE API EDITADO"
        edited = client.put(f"/api/v1/formulas/{code}", json=payload)
        assert edited.status_code == 200
        assert edited.json()["description"] == "TESTE API EDITADO"
        formula_id = edited.json()["variants"][0]["formula_id"]

        missing_grain = client.post(
            f"/api/v1/formulas/{code}/readings",
            json={
                "session_id": str(session.session_id), "measurement_role": "sample",
                "formula_id": formula_id,
            },
        )
        assert missing_grain.status_code == 400
        saved = client.post(
            f"/api/v1/formulas/{code}/readings",
            json={
                "session_id": str(session.session_id), "measurement_role": "sample",
                "formula_id": formula_id,
                "metallic_grain": "MEDIO", "notes": "chapinha de teste",
            },
        )
        assert saved.status_code == 201
        assert saved.json()["metallic_grain"] == "MEDIO"
        assert len(saved.json()["angles"]) == 5
        assert saved.json()["schema_version"] == 2
        assert saved.json()["quality_status"] in {"eligible", "review"}
        assert len(client.get(f"/api/v1/formulas/{code}/readings").json()) == 1

        duplicate = client.post(
            f"/api/v1/formulas/{code}/readings",
            json={
                "session_id": str(session.session_id), "measurement_role": "sample",
                "formula_id": formula_id,
                "metallic_grain": "MEDIO", "notes": "duplicada",
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "FORMULA_READING_ALREADY_SAVED"

        matches = client.get(
            "/api/v1/formulas/spectral-matches",
            params={"session_id": str(session.session_id), "measurement_role": "sample"},
        )
        assert matches.status_code == 200
        exact = next(item for item in matches.json()["items"] if item["code"] == code)
        assert exact["compatibility"] == 100.0
        assert exact["delta_e"] == 0.0
        assert exact["matched_measurement_id"] == session.sample.measurement_id

        removed = client.delete(f"/api/v1/formulas/{code}")
        assert removed.status_code == 204
        assert client.get(f"/api/v1/formulas/{code}").status_code == 404


def test_status_disconnected(api_bundle):
    with TestClient(api_bundle[2]) as client:
        assert client.get("/api/v1/instrument/status").json() == {
            "connected": False, "instrument": None
        }


def test_manual_connect_validation_and_disconnect(api_bundle):
    instrument, _, app = api_bundle
    with TestClient(app) as client:
        error = client.post("/api/v1/instrument/connect", json={"mode": "manual"})
        assert error.status_code == 400
        assert error.json()["error"]["code"] == "HOST_REQUIRED"
        response = client.post(
            "/api/v1/instrument/connect",
            json={"mode": "MANUAL", "host": "192.168.1.13"},
        )
        assert response.status_code == 200
        assert response.json()["instrument"]["serial"] == "SERIAL-1"
        assert client.post("/api/v1/instrument/disconnect").json() == {"connected": False}
        assert instrument.disconnect_calls >= 1


def test_multiple_auto_discovery_does_not_auto_select(api_bundle):
    instrument, _, app = api_bundle
    instrument.discoveries.append(
        DiscoveredInstrument("BYK", "192.168.1.14", 6000, 6002, serial="SERIAL-2")
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/instrument/connect", json={"mode": "auto"})
        assert response.json()["state"] == "MULTIPLE_INSTRUMENTS"
        assert len(response.json()["instruments"]) == 2
        assert instrument.connect_calls == []


def test_discovery_and_instrument_error_mapping(api_bundle):
    instrument, _, app = api_bundle
    with TestClient(app) as client:
        assert len(client.post("/api/v1/instrument/discover").json()["instruments"]) == 1
        instrument.discover_error = InstrumentError("offline")
        response = client.post("/api/v1/instrument/discover")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "INSTRUMENT_UNAVAILABLE"


def test_measurement_list_and_retrieve_preserve_five_angles(api_bundle):
    with _connected_client(api_bundle) as client:
        assert [item["measurement_id"] for item in client.get("/api/v1/measurements").json()] == [12, 13]
        result = client.get("/api/v1/measurements/12").json()
        assert [item["angle"] for item in result["angles"]] == [15, 25, 45, 75, 105]
        assert result["angles"][0]["l"] == _measurement(12).angles[MeasurementAngle.DEG_15].L


def test_missing_measurement_and_disconnected_access_use_common_errors(api_bundle):
    with TestClient(api_bundle[2]) as client:
        disconnected = client.get("/api/v1/measurements")
        assert disconnected.status_code == 503
        assert set(disconnected.json()) == {"error"}
    with _connected_client(api_bundle) as client:
        missing = client.get("/api/v1/measurements/999")
        assert missing.status_code == 404
        assert set(missing.json()["error"]) == {"code", "message", "details"}


def test_session_repository_survives_multiple_requests(api_bundle):
    with _connected_client(api_bundle) as client:
        created = client.post("/api/v1/sessions")
        assert created.status_code == 201
        session_id = created.json()["session_id"]
        assert uuid.UUID(session_id)
        fetched = client.get(f"/api/v1/sessions/{session_id}")
        assert fetched.json()["state"] == "WAITING_FOR_TARGET"
        assert fetched.json()["instrument_serial"] == "SERIAL-1"


def test_ready_session_can_replace_target_with_latest_and_preserve_sample(api_bundle):
    instrument, service, app = api_bundle
    session = _ready_session(service)
    instrument.measurements[14] = _measurement(14, offset=0.4)
    with _connected_client(api_bundle) as client:
        response = client.post(
            f"/api/v1/sessions/{session.session_id}/target/replace-with-latest"
        )
    assert response.status_code == 200
    assert response.json()["target"]["measurement_id"] == 14
    assert response.json()["sample"]["measurement_id"] == 13
    assert response.json()["state"] == "READY_FOR_COMPARISON"


def test_ready_session_can_replace_sample_with_latest(api_bundle):
    instrument, service, app = api_bundle
    session = _ready_session(service)
    instrument.measurements[14] = _measurement(14, offset=0.4)
    with _connected_client(api_bundle) as client:
        response = client.post(
            f"/api/v1/sessions/{session.session_id}/sample/replace-with-latest"
        )
    assert response.status_code == 200
    assert response.json()["target"]["measurement_id"] == 12
    assert response.json()["sample"]["measurement_id"] == 14


def test_replace_reconnects_once_after_transient_byk_timeout(api_bundle):
    instrument, service, app = api_bundle
    session = _ready_session(service)
    measurement_24 = _measurement(24, offset=0.6)
    instrument.latest_outcomes.extend([
        InstrumentTimeoutError("stale BYK connection"),
        measurement_24,
    ])

    with _connected_client(api_bundle) as client:
        response = client.post(
            f"/api/v1/sessions/{session.session_id}/sample/replace-with-latest"
        )

    assert response.status_code == 200
    assert response.json()["sample"]["measurement_id"] == 24
    # One disconnect recovers the stale socket; TestClient shutdown may add another.
    assert instrument.disconnect_calls >= 1
    assert instrument.connect_calls == [("manual", "192.168.1.13")]


def test_replace_rejects_latest_already_selected(api_bundle):
    _, service, app = api_bundle
    session = _ready_session(service)
    with _connected_client(api_bundle) as client:
        response = client.post(
            f"/api/v1/sessions/{session.session_id}/sample/replace-with-latest"
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LATEST_MEASUREMENT_ALREADY_SELECTED"


def test_missing_session_and_validation_errors_have_common_schema(api_bundle):
    with TestClient(api_bundle[2]) as client:
        missing = client.get(f"/api/v1/sessions/{uuid.uuid4()}")
        assert missing.status_code == 404
        invalid = client.get("/api/v1/sessions/not-a-uuid")
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_prepare_target_snapshot_unique_operation_and_active_conflict(api_bundle):
    instrument, service, app = api_bundle
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        first = client.post(f"/api/v1/sessions/{session_id}/target/prepare")
        assert first.status_code == 201
        assert first.json()["status"] == "PREPARED"
        assert instrument.snapshot_calls == 1
        assert uuid.UUID(first.json()["operation_id"])
        second = client.post(f"/api/v1/sessions/{session_id}/target/prepare")
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "CAPTURE_ALREADY_ACTIVE"


def test_double_sample_prepare_creates_one_effective_operation(api_bundle):
    _, service, _ = api_bundle
    session = ColorSession.create("SERIAL-1").with_target(_measurement(12))
    service.sessions.save(session)
    with _connected_client(api_bundle) as client:
        first = client.post(f"/api/v1/sessions/{session.session_id}/sample/prepare")
        second = client.post(f"/api/v1/sessions/{session.session_id}/sample/prepare")
        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "CAPTURE_ALREADY_ACTIVE"


def test_sample_prepare_requires_target(api_bundle):
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(f"/api/v1/sessions/{session_id}/sample/prepare")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TARGET_REQUIRED"


def test_cancel_operation_is_cooperative(api_bundle):
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        operation = client.post(f"/api/v1/sessions/{session_id}/target/prepare").json()
        cancelled = client.post(f"/api/v1/operations/{operation['operation_id']}/cancel")
        assert cancelled.json()["status"] == "CANCELLED"


def test_timeout_does_not_assign_old_measurement(api_bundle):
    instrument, service, app = api_bundle
    instrument.wait_outcomes.append(
        NewMeasurementTimeoutError(elapsed=1, known_count=2, last_observed_count=2, poll_count=2)
    )
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        operation = client.post(f"/api/v1/sessions/{session_id}/target/prepare").json()
        response = client.post(f"/api/v1/operations/{operation['operation_id']}/wait", json={"timeout": 1})
        assert response.status_code == 504
        assert client.get(f"/api/v1/sessions/{session_id}").json()["target"] is None


def test_successful_target_and_sample_update_session_without_changing_target(api_bundle):
    instrument, _, _ = api_bundle
    instrument.wait_outcomes.extend([_measurement(14, offset=0.1), _measurement(15, offset=0.3)])
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        target_op = client.post(f"/api/v1/sessions/{session_id}/target/prepare").json()
        assert client.post(f"/api/v1/operations/{target_op['operation_id']}/wait").json()["measurement_id"] == 14
        sample_op = client.post(f"/api/v1/sessions/{session_id}/sample/prepare").json()
        assert client.post(f"/api/v1/operations/{sample_op['operation_id']}/wait").json()["measurement_id"] == 15
        session = client.get(f"/api/v1/sessions/{session_id}").json()
        assert session["target"]["measurement_id"] == 14
        assert session["sample"]["measurement_id"] == 15
        assert session["state"] == "READY_FOR_COMPARISON"


def test_comparison_requires_ready_and_ready_result_is_sample_minus_target(api_bundle):
    _, service, app = api_bundle
    with _connected_client(api_bundle) as client:
        unready = client.post("/api/v1/sessions").json()["session_id"]
        assert client.get(f"/api/v1/sessions/{unready}/comparison").status_code == 409
        ready = _ready_session(service)
        result = client.get(f"/api/v1/sessions/{ready.session_id}/comparison").json()
        assert result["convention"] == "SAMPLE_MINUS_TARGET"
        assert len(result["angles"]) == 5
        assert result["angles"][0]["delta_l"] == pytest.approx(0.2)


def test_diagnosis_and_correction_expose_existing_core(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        diagnosis = client.get(f"/api/v1/sessions/{ready.session_id}/diagnosis").json()
        assert len(diagnosis["angles"]) == 5
        assert diagnosis["worst_angle"] in [15, 25, 45, 75, 105]
        assert set(diagnosis) >= {"front", "mid", "flop"}
        correction = client.get(f"/api/v1/sessions/{ready.session_id}/correction-needs").json()
        assert len(correction["angles"]) == 5
        assert correction["angles"][0]["lightness"] == "DARKEN"
        assert "pigment" not in str(correction).lower()


def test_pigment_candidates_expose_conflicts_risks_and_no_grams(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        result = client.post(
            f"/api/v1/sessions/{ready.session_id}/pigment-candidates",
            json={"system": "POLYESTER_BASECOAT", "finish": "METALLIC"},
        ).json()
        assert result["dosage_available"] is False
        assert result["candidates"]
        assert all("quantity_g" not in item for item in result["candidates"])
        assert any(item["conflicts"] for item in result["candidates"])
        assert any(item["risks"] for item in result["candidates"])
        bp203 = next(item for item in result["rejected_candidates"] if item["pigment_code"] == "BP203")
        assert bp203["status"] == "CONTRAINDICATED"


def test_adjustment_api_requires_operator_quantity_and_volume(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        url = f"/api/v1/sessions/{ready.session_id}/adjustments"
        missing = client.post(url, json={"system": "POLYESTER_BASECOAT", "finish": "METALLIC", "components": []})
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_adjustment_lifecycle_timeout_and_retry_do_not_duplicate_grams(api_bundle):
    instrument, service, _ = api_bundle
    ready = _ready_session(service)
    timeout = NewMeasurementTimeoutError(elapsed=1, known_count=2, last_observed_count=2, poll_count=2)
    instrument.wait_outcomes.extend([timeout, _measurement(14, offset=0.1)])
    with _connected_client(api_bundle) as client:
        created = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json={
                "system": "POLYESTER_BASECOAT",
                "finish": "METALLIC",
                "volume_ml": "450",
                "components": [{"pigment_code": "BP226", "quantity_g": "0.10"}],
                "operator_reason": "operator decision",
            },
        )
        assert created.status_code == 201
        adjustment_id = created.json()["adjustment_id"]
        assert created.json()["components"][0]["quantity_g"] == "0.10"
        assert created.json()["dosage_generated_by_system"] is False
        applied = client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied")
        assert applied.json()["lifecycle"] == "APPLIED_WAITING_FOR_AFTER"
        operation = client.post(f"/api/v1/adjustments/{adjustment_id}/after/prepare").json()
        timed_out = client.post(f"/api/v1/operations/{operation['operation_id']}/wait", json={"timeout": 1})
        assert timed_out.status_code == 504
        assert timed_out.json()["error"]["code"] == "AFTER_MEASUREMENT_TIMEOUT_ADJUSTMENT_ALREADY_APPLIED"
        still_applied = client.get(f"/api/v1/adjustments/{adjustment_id}").json()
        assert still_applied["components"] == [{"pigment_code": "BP226", "quantity_g": "0.10"}]
        retry = client.post(f"/api/v1/adjustments/{adjustment_id}/after/retry").json()
        completed = client.post(f"/api/v1/operations/{retry['operation_id']}/wait")
        assert completed.status_code == 200
        final = client.get(f"/api/v1/adjustments/{adjustment_id}").json()
        assert final["lifecycle"] == "COMPLETED"
        assert final["components"] == [{"pigment_code": "BP226", "quantity_g": "0.10"}]
        assert client.get(f"/api/v1/sessions/{ready.session_id}").json()["sample"]["measurement_id"] == 14


def test_adjustment_repository_lists_between_requests(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        response = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json={
                "system": "POLYESTER_BASECOAT", "finish": "METALLIC",
                "volume_ml": "900",
                "components": [{"pigment_code": "BP226", "quantity_g": "0.05"}],
                "operator_reason": "operator supplied",
            },
        )
        adjustment_id = response.json()["adjustment_id"]
        listed = client.get(f"/api/v1/sessions/{ready.session_id}/adjustments").json()
        assert [item["adjustment_id"] for item in listed] == [adjustment_id]


def test_completed_adjustment_exposes_domain_response_outcome_and_measurement_chain(api_bundle):
    instrument, service, _ = api_bundle
    ready = _ready_session(service)
    instrument.wait_outcomes.append(_measurement(14, offset=0.1))
    with _connected_client(api_bundle) as client:
        created = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(),
        ).json()
        adjustment_id = created["adjustment_id"]
        client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied")
        operation = client.post(
            f"/api/v1/adjustments/{adjustment_id}/after/prepare"
        ).json()
        assert client.post(f"/api/v1/operations/{operation['operation_id']}/wait").status_code == 200

        result = client.get(f"/api/v1/adjustments/{adjustment_id}").json()
        assert result["target"]["measurement_id"] == 12
        assert result["before"]["measurement_id"] == 13
        assert result["after"]["measurement_id"] == 14
        assert len(result["observed_response"]) == 5
        assert len(result["outcomes"]) == 5
        assert result["before_comparison"]["sample_id"] == 13
        assert result["after_comparison"]["sample_id"] == 14
        assert result["worst_angle_before"] in [15, 25, 45, 75, 105]
        assert result["dosage_generated_by_system"] is False
        assessment = result["assessment"]
        assert assessment["verdict"] in {"IMPROVED", "WORSENED", "MIXED", "UNCHANGED"}
        assert [item["angle"] for item in assessment["angles"]] == [15, 25, 45, 75, 105]
        assert [axis["axis"] for axis in assessment["angles"][0]["axes"]] == ["L", "A", "B"]
        assert result["operator_disagrees_with_instrument"] is False


def test_pending_adjustment_is_recovered_after_service_restart(tmp_path):
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    instrument = FakeInstrument()
    first = MandacorApiService(instrument, pending_repository=repository)
    first.connected_info = INFO
    instrument.connected = True
    ready = _ready_session(first)
    pending = first.create_adjustment(
        ready.session_id,
        PaintContext(PaintSystem.POLYESTER_BASECOAT, FinishType.METALLIC),
        "450",
        (AdjustmentComponent("BP226", "0.10"),),
        "operador",
        base_identifier=None,
        color_description=None,
    )
    applied = first.confirm_adjustment_applied(pending.adjustment_id)

    restarted = MandacorApiService(FakeInstrument(), pending_repository=repository)
    app = create_app(restarted)
    with TestClient(app) as client:
        recovered = client.get("/api/v1/adjustments/pending")
        assert recovered.status_code == 200
        assert recovered.json()["adjustment_id"] == str(applied.adjustment_id)
        assert recovered.json()["lifecycle"] == "APPLIED_WAITING_FOR_AFTER"
        session = client.get(f"/api/v1/sessions/{applied.session_id}").json()
        assert session["target"]["measurement_id"] == 12
        assert session["sample"]["measurement_id"] == 13


def test_abandon_preserves_applied_record_and_removes_it_from_active_pending(api_bundle, tmp_path):
    instrument, _, _ = api_bundle
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    service = MandacorApiService(instrument, pending_repository=repository)
    ready = _ready_session(service)
    app = create_app(service)
    with _connected_client((instrument, service, app)) as client:
        created = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(),
        ).json()
        client.post(f"/api/v1/adjustments/{created['adjustment_id']}/confirm-applied")
        abandoned = client.post(
            f"/api/v1/adjustments/{created['adjustment_id']}/abandon",
            json={"observation": "placa indisponível para leitura AFTER"},
        )
        assert abandoned.status_code == 200
        assert abandoned.json()["lifecycle"] == "ABANDONED_AFTER_APPLICATION"
        assert client.get("/api/v1/adjustments/pending").json() is None
        assert repository.load().adjustment_id == uuid.UUID(created["adjustment_id"])


def test_operator_feedback_updates_completed_trial_without_changing_quantities(api_bundle):
    instrument, service, _ = api_bundle
    ready = _ready_session(service)
    instrument.wait_outcomes.append(_measurement(14, offset=0.1))
    with _connected_client(api_bundle) as client:
        created = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(quantity="0.07"),
        ).json()
        adjustment_id = created["adjustment_id"]
        client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied")
        operation = client.post(f"/api/v1/adjustments/{adjustment_id}/after/prepare").json()
        client.post(f"/api/v1/operations/{operation['operation_id']}/wait")
        feedback = client.post(
            f"/api/v1/adjustments/{adjustment_id}/feedback",
            json={
                "visual_result": "BETTER",
                "operator_status": "ACCEPTED",
                "observations": "melhora visual confirmada",
            },
        )
        assert feedback.status_code == 200
        body = feedback.json()
        assert body["visual_result"] == "BETTER"
        assert body["operator_status"] == "ACCEPTED"
        assert body["observations"] == "melhora visual confirmada"
        assert body["components"] == [{"pigment_code": "BP226", "quantity_g": "0.07"}]


def test_active_pending_blocks_a_second_adjustment(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        first = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(),
        ).json()
        client.post(f"/api/v1/adjustments/{first['adjustment_id']}/confirm-applied")
        conflict = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(quantity="0.20"),
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "PENDING_ADJUSTMENT_EXISTS"
        assert conflict.json()["error"]["details"]["adjustment_id"] == first["adjustment_id"]


def test_double_confirm_applied_never_applies_quantity_twice(api_bundle, tmp_path):
    instrument, _, _ = api_bundle
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    service = MandacorApiService(instrument, pending_repository=repository)
    ready = _ready_session(service)
    app = create_app(service)
    with _connected_client((instrument, service, app)) as client:
        adjustment_id = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(),
        ).json()["adjustment_id"]
        assert client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied").status_code == 200
        duplicate = client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied")
        assert duplicate.status_code == 409
        pending = repository.load()
        assert pending.adjustment_id == uuid.UUID(adjustment_id)
        assert pending.components == (AdjustmentComponent("BP226", "0.10"),)


def test_double_after_prepare_creates_one_effective_operation(api_bundle):
    _, service, _ = api_bundle
    ready = _ready_session(service)
    with _connected_client(api_bundle) as client:
        adjustment_id = client.post(
            f"/api/v1/sessions/{ready.session_id}/adjustments",
            json=_adjustment_payload(),
        ).json()["adjustment_id"]
        client.post(f"/api/v1/adjustments/{adjustment_id}/confirm-applied")
        first = client.post(f"/api/v1/adjustments/{adjustment_id}/after/prepare")
        second = client.post(f"/api/v1/adjustments/{adjustment_id}/after/prepare")
        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "CAPTURE_ALREADY_ACTIVE"


def test_shutdown_cancels_waits_and_disconnects_instrument(api_bundle):
    instrument, _, app = api_bundle
    with _connected_client(api_bundle) as client:
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        operation_id = client.post(
            f"/api/v1/sessions/{session_id}/target/prepare"
        ).json()["operation_id"]
    operation = api_bundle[1].operations.get(uuid.UUID(operation_id))
    assert operation.cancellation.is_set()
    assert instrument.connected is False
    assert instrument.disconnect_calls >= 1


def test_corrupt_recovery_does_not_crash_server_and_state_is_not_assumed_empty(tmp_path):
    path = tmp_path / "pending.json"
    path.write_text("{truncated", encoding="utf-8")
    service = MandacorApiService(
        FakeInstrument(), pending_repository=JsonPendingAdjustmentRepository(path)
    )
    assert service.recovery_error == "RECOVERY_FILE_INVALID"
    with TestClient(create_app(service)) as client:
        health = client.get("/health").json()
        assert health["status"] == "ok"
        assert health["recovery"] == "ERROR"
        response = client.get("/api/v1/adjustments/pending")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "RECOVERY_FILE_INVALID"
        assert response.json()["error"]["request_id"]


def test_unexpected_error_has_request_id_and_standard_envelope(api_bundle):
    app = api_bundle[2]

    @app.get("/test/unexpected")
    def unexpected():
        raise RuntimeError("sensitive internal failure")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/unexpected", headers={"X-Request-ID": "support-123"})
        assert response.status_code == 500
        assert response.headers["X-Request-ID"] == "support-123"
        assert response.json() == {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "an unexpected server error occurred",
                "details": {},
                "request_id": "support-123",
            }
        }
        assert "sensitive internal failure" not in response.text


def test_openapi_docs_and_cors_configuration(api_bundle):
    instrument, service, _ = api_bundle
    app = create_app(service, settings=ApiConfig(cors_origins=("http://localhost:8081",)))
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200
        response = client.options(
            "/api/v1/health",
            headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "GET"},
        )
        assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    with pytest.raises(ValueError, match="wildcard"):
        ApiConfig(cors_origins=("*",))
