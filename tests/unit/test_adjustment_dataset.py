from __future__ import annotations

import csv
import uuid

from mandacor.application.adjustment_dataset import (
    COMPONENT_DATASET_COLUMNS,
    MAIN_DATASET_COLUMNS,
    AdjustmentDatasetExporter,
    trial_to_component_rows,
    trial_to_dataset_row,
)
from mandacor.domain.adjustments import (
    AdjustmentComponent,
    OperatorTrialStatus,
    VisualResult,
    complete_adjustment_trial,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle

from test_adjustments import LATER, _applied, _measurement, _session


def _trial(*, components=None, visual=VisualResult.UNKNOWN, status=OperatorTrialStatus.UNKNOWN):
    target = _measurement(12, LabValue(50.1234567890123, -0.1234567890123, 5.9876543210987))
    before = _measurement(13, LabValue(49.1111111111111, 0.2222222222222, 6.3333333333333))
    after = _measurement(14, LabValue(50.0000000000001, -0.0000000000002, 6.0000000000003))
    pending = _applied(
        session=_session(target, before),
        components=components,
    )
    return complete_adjustment_trial(
        pending,
        after,
        visual_result=visual,
        operator_status=status,
        now=lambda: LATER,
    )


def test_dataset_has_required_columns_in_deterministic_order():
    assert MAIN_DATASET_COLUMNS[:7] == (
        "id_ajuste", "data", "sistema", "finish_type", "base", "cor_veiculo", "volume_tinta_ml"
    )
    assert MAIN_DATASET_COLUMNS[-7:] == (
        "session_id", "target_measurement_id", "before_measurement_id",
        "after_measurement_id", "instrument_serial", "component_count", "learning_eligibility"
    )
    assert COMPONENT_DATASET_COLUMNS == ("adjustment_id", "pigment_code", "quantity_g")


def test_dataset_preserves_five_target_before_after_angles_and_full_precision():
    row = trial_to_dataset_row(_trial())
    for prefix in ("leitura_alvo", "leitura_antes", "leitura_depois"):
        for angle in MeasurementAngle:
            for axis in ("L", "a", "b"):
                assert f"{prefix}_{int(angle)}_{axis}" in row
    assert row["leitura_alvo_15_L"] == repr(50.1234567890123)
    assert row["leitura_antes_105_a"] == repr(0.2222222222222)
    assert row["leitura_depois_45_b"] == repr(6.0000000000003)


def test_single_component_exports_exact_pigment_and_quantity():
    row = trial_to_dataset_row(_trial())
    assert row["pigmento_adicionado"] == "BP226"
    assert row["quantidade_g"] == "0.10"
    assert row["component_count"] == "1"
    assert row["learning_eligibility"] == "isolated_single_component"


def test_multi_component_uses_normalized_component_rows_without_attribution():
    components = (
        AdjustmentComponent("BP226", "0.10"),
        AdjustmentComponent("BP282", "0.50"),
    )
    trial = _trial(components=components)
    main = trial_to_dataset_row(trial)
    rows = trial_to_component_rows(trial)
    assert main["pigmento_adicionado"] == ""
    assert main["quantidade_g"] == ""
    assert main["component_count"] == "2"
    assert main["learning_eligibility"] == "mixed_components"
    assert [(row["pigment_code"], row["quantity_g"]) for row in rows] == [
        ("BP226", "0.10"), ("BP282", "0.50")
    ]


def test_dataset_has_stable_adjustment_id_and_iso_datetime():
    trial = _trial()
    row = trial_to_dataset_row(trial)
    assert row["id_ajuste"] == str(trial.adjustment_id)
    assert uuid.UUID(row["id_ajuste"]) == trial.adjustment_id
    assert row["data"] == trial.completed_at.isoformat()
    assert row["data"].endswith("+00:00")


def test_dataset_does_not_invent_optional_operator_feedback():
    row = trial_to_dataset_row(_trial())
    assert row["resultado_visual"] == ""
    assert row["status"] == ""
    assert row["observacoes"] == ""


def test_operator_feedback_is_exported_only_when_provided():
    trial = _trial(visual=VisualResult.BETTER, status=OperatorTrialStatus.ACCEPTED)
    row = trial_to_dataset_row(trial)
    assert row["resultado_visual"] == "better"
    assert row["status"] == "accepted"


def test_csv_export_is_utf8_deterministic_and_normalized(tmp_path):
    trial = _trial(components=(
        AdjustmentComponent("BP226", "0.10"),
        AdjustmentComponent("BP282", "0.50"),
    ))
    main = tmp_path / "adjustments.csv"
    components = tmp_path / "adjustment_components.csv"
    counts = AdjustmentDatasetExporter().export((trial,), main, components)
    assert counts == (1, 2)
    with main.open(encoding="utf-8", newline="") as stream:
        main_rows = list(csv.DictReader(stream))
    with components.open(encoding="utf-8", newline="") as stream:
        component_rows = list(csv.DictReader(stream))
    assert tuple(main_rows[0]) == MAIN_DATASET_COLUMNS
    assert tuple(component_rows[0]) == COMPONENT_DATASET_COLUMNS
    assert len(main_rows) == 1
    assert len(component_rows) == 2


def test_csv_append_preserves_prior_history_and_rejects_wrong_schema(tmp_path):
    exporter = AdjustmentDatasetExporter()
    first = _trial()
    second = _trial()
    main = tmp_path / "adjustments.csv"
    components = tmp_path / "components.csv"
    exporter.append(first, main, components)
    exporter.append(second, main, components)
    with main.open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 2
    with components.open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 2
    main.write_text("wrong,header\n", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="header"):
        exporter.append(first, main, components)
