from pathlib import Path
import json
import shutil
import sqlite3

import pytest

from mandacor.application.formula_training_dataset import FormulaTrainingDatasetExporter
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle

from mandacor.infrastructure.storage.formula_sqlite import (
    DuplicateFormulaReadingError,
    FormulaCatalogNotFoundError,
    SqliteFormulaCatalog,
)


CATALOG = Path(__file__).resolve().parents[2] / "data" / "formulas.sqlite3"


@pytest.fixture(scope="module")
def catalog():
    return SqliteFormulaCatalog(CATALOG)


def test_imported_catalog_preserves_all_current_skymix_records(catalog):
    assert catalog.metadata() == {
        "source": "skymix/Database/SkylacDb.accdb",
        "products": "12198",
        "formulas": "14069",
        "components": "97677",
        "source_components": "109541",
    }


def test_search_is_accent_insensitive_and_filters_system(catalog):
    result = catalog.search("vermelho fogo scania", "POLIESTER", limit=10)
    assert result.total >= 1
    assert any(item.code == "210009850101" for item in result.items)


def test_commercial_code_uses_system_prefix_and_finds_internal_variants(catalog):
    polyester = catalog.search("210-03121")
    assert any(item.code == "210031210101" for item in polyester.items)
    assert all(item.display_code == "210-03121" for item in polyester.items)

    pu = catalog.search("61003121")
    assert any(item.code == "610031210119" for item in pu.items)
    assert all(item.display_code == "610-03121" for item in pu.items)


def test_search_supports_additional_catalog_filters(catalog):
    result = catalog.search(
        "",
        "POLIESTER",
        manufacturer="FIAT",
        year="1995",
        finish="LISA",
        universal_code="178",
    )
    assert any(item.display_code == "210-03121" for item in result.items)


def test_formula_detail_contains_original_component_quantities(catalog):
    formula = catalog.get("210009850101")
    assert formula.description == "VERMELHO FOGO LISA"
    assert formula.system == "POLIESTER"
    assert formula.display_code == "210-00985"
    assert formula.variants[0].total_weight_g == pytest.approx(872.3)
    assert [(item.base_code, item.weight_g) for item in formula.variants[0].components] == [
        ("BP240", 14.0),
        ("BP215", 30.5),
        ("BP235", 235.5),
        ("BP242", 295.7),
        ("TH700", 296.6),
    ]


def test_formula_uses_only_latest_skymix_revision_for_same_version(catalog):
    formula = catalog.get("210023200101")
    assert formula.display_code == "210-02320"
    assert formula.variants[0].updated_at == "2010-04-01T00:00"
    assert formula.variants[0].total_weight_g == pytest.approx(903.9)
    assert [(item.base_code, item.weight_g) for item in formula.variants[0].components] == [
        ("BP218", 3.3),
        ("BP216", 11.5),
        ("BP299", 54.2),
        ("TH700", 307.3),
        ("BP240", 527.6),
    ]


def test_missing_formula_has_explicit_error(catalog):
    with pytest.raises(FormulaCatalogNotFoundError):
        catalog.get("INEXISTENTE")


def test_user_can_create_edit_delete_formula_and_save_metallic_reading(tmp_path):
    editable_path = tmp_path / "formulas.sqlite3"
    shutil.copy2(CATALOG, editable_path)
    editable = SqliteFormulaCatalog(editable_path)
    payload = {
        "code": "210-99999", "description": "COR DE TESTE METALICA", "year": "2026",
        "universal_code": "TESTE", "nuance": "A", "manufacturer": "MANDACOR",
        "observations": "cadastro do usuário", "system": "POLIESTER",
        "finish_label": "METALICO", "variants": [{
            "condition": "DILUIDO", "package": "1 Quarto", "version": 1,
            "components": [
                {"base_code": "BP218", "base_name": "Preto", "weight_g": "3.3"},
                {"base_code": "BP240", "base_name": "Branco", "weight_g": "900.6"},
            ],
        }],
    }
    created = editable.create(payload)
    assert created.display_code == "210-99999"
    assert created.origin == "USER"
    assert created.variants[0].total_weight_g == pytest.approx(903.9)

    payload["description"] = "COR DE TESTE EDITADA"
    payload["variants"][0]["components"][0]["weight_g"] = "4.0"
    updated = editable.update(created.code, payload)
    assert updated.description == "COR DE TESTE EDITADA"
    assert updated.variants[0].total_weight_g == pytest.approx(904.6)

    measurement = Measurement(
        77,
        {angle: LabValue(50 + int(angle) / 100, 1, -1) for angle in MeasurementAngle},
        guid="measurement-77", instrument_serial="BYK-1",
    )
    with pytest.raises(ValueError, match="metallic_grain"):
        editable.save_reading(
            created.code, session_id="session-1", role="sample",
            formula_id=updated.variants[0].formula_id,
            metallic_grain=None, notes="", measurement=measurement,
        )
    reading = editable.save_reading(
        created.code, session_id="session-1", role="sample",
        formula_id=updated.variants[0].formula_id,
        metallic_grain="MEDIO_FINO", notes="chapinha", measurement=measurement,
    )
    assert reading["metallic_grain"] == "MEDIO_FINO"
    assert len(reading["angles"]) == 5
    assert reading["schema_version"] == 2
    assert len(reading["measurement_fingerprint"]) == 64
    assert reading["quality_status"] == "review"
    assert "missing_measurement_timestamp" in reading["quality_issues"]
    assert editable.get(created.code).reading_count == 1

    with pytest.raises(DuplicateFormulaReadingError):
        editable.save_reading(
            created.code, session_id="session-2", role="sample",
            formula_id=updated.variants[0].formula_id,
            metallic_grain="MEDIO_FINO", notes="duplicada", measurement=measurement,
        )

    matches = editable.spectral_matches(measurement)
    exact = next(item for item in matches["items"] if item["product"].code == created.code)
    assert exact["compatibility"] == 100.0
    assert exact["delta_e"] == 0.0
    assert exact["measurement_id"] == 77

    output = tmp_path / "training" / "formula_spectra.jsonl"
    manifest = FormulaTrainingDatasetExporter().export(
        editable, output, eligible_only=False
    )
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert manifest["record_count"] == 1
    assert records[0]["schema"] == "mandacor.paint-spectrum.v1"
    assert records[0]["group_key"] == created.code
    assert len(records[0]["features"]["spectrum_lab_multiangle"]) == 5
    assert records[0]["label"]["formula_snapshot"]["variants"][0]["components"][0]["weight_g"] == 4.0
    assert output.with_suffix(".jsonl.manifest.json").exists()

    editable.delete(created.code)
    with pytest.raises(FormulaCatalogNotFoundError):
        editable.get(created.code)
    with sqlite3.connect(editable_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM paint_readings").fetchone()[0] == 1
