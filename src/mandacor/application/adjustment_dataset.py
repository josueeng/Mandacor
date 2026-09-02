from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping

from mandacor.domain.adjustments import (
    CompletedAdjustmentTrial,
    OperatorTrialStatus,
    VisualResult,
)
from mandacor.domain.measurements import Measurement, REQUIRED_MEASUREMENT_ANGLES


def _lab_columns(prefix: str) -> tuple[str, ...]:
    return tuple(
        f"{prefix}_{int(angle)}_{axis}"
        for angle in REQUIRED_MEASUREMENT_ANGLES
        for axis in ("L", "a", "b")
    )


MAIN_DATASET_COLUMNS = (
    "dataset_schema_version",
    "id_ajuste",
    "data",
    "created_at",
    "applied_at",
    "completed_at",
    "sistema",
    "finish_type",
    "base",
    "cor_veiculo",
    "volume_tinta_ml",
    *_lab_columns("leitura_alvo"),
    *_lab_columns("leitura_antes"),
    "pigmento_adicionado",
    "quantidade_g",
    "motivo_do_ajuste",
    *_lab_columns("leitura_depois"),
    "resultado_visual",
    "status",
    "observacoes",
    "session_id",
    "target_measurement_id",
    "target_measurement_guid",
    "target_measurement_timestamp",
    "before_measurement_id",
    "before_measurement_guid",
    "before_measurement_timestamp",
    "after_measurement_id",
    "after_measurement_guid",
    "after_measurement_timestamp",
    "instrument_serial",
    "component_count",
    "learning_eligibility",
    "data_quality_flags",
)

COMPONENT_DATASET_COLUMNS = (
    "adjustment_id",
    "pigment_code",
    "quantity_g",
)


def _measurement_values(prefix: str, measurement: Measurement) -> dict[str, str]:
    values: dict[str, str] = {}
    for angle in REQUIRED_MEASUREMENT_ANGLES:
        lab = measurement.angles[angle]
        values[f"{prefix}_{int(angle)}_L"] = repr(lab.L)
        values[f"{prefix}_{int(angle)}_a"] = repr(lab.a)
        values[f"{prefix}_{int(angle)}_b"] = repr(lab.b)
    return values


def trial_to_dataset_row(trial: CompletedAdjustmentTrial) -> Mapping[str, str]:
    single = trial.components[0] if len(trial.components) == 1 else None
    values = {
        "dataset_schema_version": "mandacor.adjustment-effect.v2",
        "id_ajuste": str(trial.adjustment_id),
        "data": trial.completed_at.isoformat(),
        "created_at": trial.created_at.isoformat(),
        "applied_at": trial.applied_at.isoformat(),
        "completed_at": trial.completed_at.isoformat(),
        "sistema": trial.paint_context.system.value,
        "finish_type": trial.paint_context.finish_type.value,
        "base": trial.base_identifier or "",
        "cor_veiculo": trial.color_description or "",
        "volume_tinta_ml": format(trial.volume_ml, "f"),
        "pigmento_adicionado": single.pigment_code if single else "",
        "quantidade_g": format(single.quantity_g, "f") if single else "",
        "motivo_do_ajuste": trial.operator_reason,
        "resultado_visual": (
            "" if trial.visual_result is VisualResult.UNKNOWN else trial.visual_result.value
        ),
        "status": (
            "" if trial.operator_status is OperatorTrialStatus.UNKNOWN
            else trial.operator_status.value
        ),
        "observacoes": trial.observations or "",
        "session_id": str(trial.session_id),
        "target_measurement_id": str(trial.target.measurement_id),
        "target_measurement_guid": trial.target.guid or "",
        "target_measurement_timestamp": (
            trial.target.timestamp.isoformat()
            if trial.target.timestamp else trial.target.timestamp_raw or ""
        ),
        "before_measurement_id": str(trial.before.measurement_id),
        "before_measurement_guid": trial.before.guid or "",
        "before_measurement_timestamp": (
            trial.before.timestamp.isoformat()
            if trial.before.timestamp else trial.before.timestamp_raw or ""
        ),
        "after_measurement_id": str(trial.after.measurement_id),
        "after_measurement_guid": trial.after.guid or "",
        "after_measurement_timestamp": (
            trial.after.timestamp.isoformat()
            if trial.after.timestamp else trial.after.timestamp_raw or ""
        ),
        "instrument_serial": trial.instrument_serial or "",
        "component_count": str(len(trial.components)),
        "learning_eligibility": trial.learning_eligibility.value,
        "data_quality_flags": ",".join(
            sorted(flag.value for flag in trial.data_quality_flags)
        ),
    }
    values.update(_measurement_values("leitura_alvo", trial.target))
    values.update(_measurement_values("leitura_antes", trial.before))
    values.update(_measurement_values("leitura_depois", trial.after))
    return {column: values[column] for column in MAIN_DATASET_COLUMNS}


def trial_to_component_rows(trial: CompletedAdjustmentTrial) -> tuple[Mapping[str, str], ...]:
    return tuple(
        {
            "adjustment_id": str(trial.adjustment_id),
            "pigment_code": component.pigment_code,
            "quantity_g": format(component.quantity_g, "f"),
        }
        for component in trial.components
    )


class AdjustmentDatasetExporter:
    def export(
        self,
        trials: Iterable[CompletedAdjustmentTrial],
        main_csv: Path,
        components_csv: Path,
    ) -> tuple[int, int]:
        trial_values = tuple(trials)
        main_csv.parent.mkdir(parents=True, exist_ok=True)
        components_csv.parent.mkdir(parents=True, exist_ok=True)
        with main_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=MAIN_DATASET_COLUMNS)
            writer.writeheader()
            writer.writerows(trial_to_dataset_row(trial) for trial in trial_values)
        component_rows = tuple(
            row for trial in trial_values for row in trial_to_component_rows(trial)
        )
        with components_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=COMPONENT_DATASET_COLUMNS)
            writer.writeheader()
            writer.writerows(component_rows)
        return len(trial_values), len(component_rows)

    def append(
        self,
        trial: CompletedAdjustmentTrial,
        main_csv: Path,
        components_csv: Path,
    ) -> None:
        main_csv.parent.mkdir(parents=True, exist_ok=True)
        components_csv.parent.mkdir(parents=True, exist_ok=True)
        self._append_rows(
            main_csv,
            MAIN_DATASET_COLUMNS,
            (trial_to_dataset_row(trial),),
        )
        self._append_rows(
            components_csv,
            COMPONENT_DATASET_COLUMNS,
            trial_to_component_rows(trial),
        )

    @staticmethod
    def _append_rows(
        path: Path,
        columns: tuple[str, ...],
        rows: Iterable[Mapping[str, str]],
    ) -> None:
        exists_with_content = path.exists() and path.stat().st_size > 0
        if exists_with_content:
            with path.open(encoding="utf-8", newline="") as stream:
                header = next(csv.reader(stream), None)
            if tuple(header or ()) != columns:
                raise ValueError(f"existing CSV header does not match schema: {path}")
        with path.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            if not exists_with_content:
                writer.writeheader()
            writer.writerows(rows)
