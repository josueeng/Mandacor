from __future__ import annotations

import json
import os

import pytest

from mandacor.domain.adjustments import AdjustmentLifecycle
from mandacor.infrastructure.storage.pending_adjustment_json import (
    JsonPendingAdjustmentRepository,
    RecoveryFileInvalidError,
    pending_from_dict,
    pending_to_dict,
)

from test_adjustments import ADJUSTMENT_ID, _applied, _planned


def test_applied_pending_round_trips_with_exact_decimal_and_measurements(tmp_path):
    path = tmp_path / "pending.json"
    repository = JsonPendingAdjustmentRepository(path)
    pending = _applied()
    repository.save(pending)
    restored = repository.load()
    assert restored == pending
    assert restored.adjustment_id == ADJUSTMENT_ID
    assert format(restored.components[0].quantity_g, "f") == "0.10"
    assert format(restored.volume_ml, "f") == "450"
    assert restored.target.angles == pending.target.angles
    assert restored.before.angles == pending.before.angles


def test_document_is_versioned_and_contains_recovery_identity():
    data = pending_to_dict(_applied())
    assert data["schema_version"] == 1
    assert data["adjustment_id"] == str(ADJUSTMENT_ID)
    assert data["session_id"]
    assert data["target"]["measurement_id"] == 12
    assert data["before"]["measurement_id"] == 13
    assert data["lifecycle"] == "applied_waiting_for_after"


def test_unsupported_schema_is_rejected():
    data = pending_to_dict(_applied())
    data["schema_version"] = 999
    with pytest.raises(ValueError, match="schema"):
        pending_from_dict(data)


def test_planned_adjustment_cannot_be_persisted_as_applied(tmp_path):
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    with pytest.raises(ValueError, match="applied"):
        repository.save(_planned())


def test_clear_requires_matching_adjustment_id_and_is_not_silent(tmp_path):
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    repository.save(_applied())
    with pytest.raises(ValueError, match="different"):
        repository.clear(__import__("uuid").uuid4())
    assert repository.load() is not None
    repository.clear(ADJUSTMENT_ID)
    assert repository.load() is None


def test_abandoned_after_application_is_preserved_not_deleted(tmp_path):
    repository = JsonPendingAdjustmentRepository(tmp_path / "pending.json")
    abandoned = _applied().abandon_after_application("explicit operator discard")
    repository.save(abandoned)
    assert repository.load().lifecycle is AdjustmentLifecycle.ABANDONED_AFTER_APPLICATION


def test_json_is_utf8_and_decimal_is_plain_text(tmp_path):
    path = tmp_path / "pending.json"
    JsonPendingAdjustmentRepository(path).save(_applied())
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["components"][0]["quantity_g"] == "0.10"
    assert raw["volume_ml"] == "450"


def test_critical_json_write_is_atomic_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "pending.json"
    repository = JsonPendingAdjustmentRepository(path)
    replacements = []
    real_replace = os.replace

    def recording_replace(source, target):
        replacements.append((source, target))
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)
    repository.save(_applied())
    assert replacements and replacements[0][1] == path
    assert list(tmp_path.glob("*.tmp")) == []
    assert repository.load() == _applied()


def test_corrupt_recovery_raises_specific_error_without_modifying_file(tmp_path):
    path = tmp_path / "pending.json"
    original = b'{"schema_version":'
    path.write_bytes(original)
    with pytest.raises(RecoveryFileInvalidError, match="critical recovery"):
        JsonPendingAdjustmentRepository(path).load()
    assert path.read_bytes() == original
