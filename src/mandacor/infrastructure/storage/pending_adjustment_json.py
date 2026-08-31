from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from mandacor.domain.adjustments import (
    AdjustmentComponent,
    AdjustmentLifecycle,
    PendingAdjustment,
)
from mandacor.domain.measurements import LabValue, Measurement, MeasurementAngle
from mandacor.domain.pigments import FinishType, PaintContext, PaintSystem


PENDING_SCHEMA_VERSION = 1


class RecoveryFileInvalidError(ValueError):
    """A critical recovery file exists but cannot be trusted."""


def _measurement_to_dict(measurement: Measurement) -> dict[str, object]:
    return {
        "measurement_id": measurement.measurement_id,
        "guid": measurement.guid,
        "timestamp": measurement.timestamp.isoformat() if measurement.timestamp else None,
        "timestamp_raw": measurement.timestamp_raw,
        "name": measurement.name,
        "instrument_serial": measurement.instrument_serial,
        "temperature": measurement.temperature,
        "angles": {
            str(int(angle)): {"L": lab.L, "a": lab.a, "b": lab.b}
            for angle, lab in measurement.angles.items()
        },
    }


def _measurement_from_dict(data: dict[str, object]) -> Measurement:
    raw_angles = data["angles"]
    if not isinstance(raw_angles, dict):
        raise ValueError("pending measurement angles must be an object")
    angles = {
        MeasurementAngle(int(angle)): LabValue(
            value["L"], value["a"], value["b"]
        )
        for angle, value in raw_angles.items()
    }
    timestamp_text = data.get("timestamp")
    return Measurement(
        int(data["measurement_id"]),
        angles,
        guid=data.get("guid"),
        timestamp=(datetime.fromisoformat(timestamp_text) if timestamp_text else None),
        timestamp_raw=data.get("timestamp_raw"),
        name=data.get("name"),
        instrument_serial=data.get("instrument_serial"),
        temperature=data.get("temperature"),
    )


def pending_to_dict(pending: PendingAdjustment) -> dict[str, object]:
    return {
        "schema_version": PENDING_SCHEMA_VERSION,
        "adjustment_id": str(pending.adjustment_id),
        "session_id": str(pending.session_id),
        "instrument_serial": pending.instrument_serial,
        "target": _measurement_to_dict(pending.target),
        "before": _measurement_to_dict(pending.before),
        "paint_context": {
            "system": pending.paint_context.system.value,
            "finish_type": pending.paint_context.finish_type.value,
        },
        "volume_ml": format(pending.volume_ml, "f"),
        "components": [
            {
                "pigment_code": item.pigment_code,
                "quantity_g": format(item.quantity_g, "f"),
            }
            for item in pending.components
        ],
        "operator_reason": pending.operator_reason,
        "lifecycle": pending.lifecycle.value,
        "created_at": pending.created_at.isoformat(),
        "applied_at": pending.applied_at.isoformat() if pending.applied_at else None,
        "observations": pending.observations,
        "base_identifier": pending.base_identifier,
        "color_description": pending.color_description,
    }


def pending_from_dict(data: dict[str, object]) -> PendingAdjustment:
    if data.get("schema_version") != PENDING_SCHEMA_VERSION:
        raise ValueError("unsupported pending adjustment schema version")
    context = data["paint_context"]
    if not isinstance(context, dict):
        raise ValueError("paint_context must be an object")
    raw_components = data["components"]
    if not isinstance(raw_components, list):
        raise ValueError("components must be an array")
    return PendingAdjustment(
        adjustment_id=uuid.UUID(str(data["adjustment_id"])),
        session_id=uuid.UUID(str(data["session_id"])),
        instrument_serial=data.get("instrument_serial"),
        target=_measurement_from_dict(data["target"]),
        before=_measurement_from_dict(data["before"]),
        paint_context=PaintContext(
            PaintSystem(context["system"]), FinishType(context["finish_type"])
        ),
        volume_ml=Decimal(str(data["volume_ml"])),
        components=tuple(
            AdjustmentComponent(item["pigment_code"], Decimal(str(item["quantity_g"])))
            for item in raw_components
        ),
        operator_reason=str(data["operator_reason"]),
        lifecycle=AdjustmentLifecycle(data["lifecycle"]),
        created_at=datetime.fromisoformat(str(data["created_at"])),
        applied_at=(
            datetime.fromisoformat(str(data["applied_at"]))
            if data.get("applied_at")
            else None
        ),
        observations=data.get("observations"),
        base_identifier=data.get("base_identifier"),
        color_description=data.get("color_description"),
    )


class JsonPendingAdjustmentRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def save(self, pending: PendingAdjustment) -> None:
        if pending.lifecycle not in {
            AdjustmentLifecycle.APPLIED_WAITING_FOR_AFTER,
            AdjustmentLifecycle.ABANDONED_AFTER_APPLICATION,
        }:
            raise ValueError("only applied or explicitly abandoned adjustments are persisted")
        document = json.dumps(pending_to_dict(pending), indent=2, sort_keys=True) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(document)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, self.path)
                directory_descriptor = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            except BaseException:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise

    def load(self) -> PendingAdjustment | None:
        with self._lock:
            if not self.path.exists():
                return None
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("pending adjustment document must be an object")
                return pending_from_dict(data)
            except (OSError, ValueError, TypeError, KeyError) as error:
                raise RecoveryFileInvalidError(
                    f"critical recovery file is invalid: {self.path}"
                ) from error

    def clear(self, adjustment_id: uuid.UUID) -> None:
        with self._lock:
            pending = self.load()
            if pending is None:
                return
            if pending.adjustment_id != adjustment_id:
                raise ValueError("refusing to clear a different pending adjustment")
            self.path.unlink()
