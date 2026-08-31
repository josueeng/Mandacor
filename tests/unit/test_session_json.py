from __future__ import annotations

import pytest

from mandacor.api.service import InMemorySessionRepository
from mandacor.infrastructure.storage.pending_adjustment_json import RecoveryFileInvalidError
from mandacor.infrastructure.storage.session_json import JsonSessionRepository

from test_adjustments import SESSION_ID, _session


def test_session_survives_repository_restart(tmp_path):
    path = tmp_path / "sessions.json"
    first = InMemorySessionRepository(JsonSessionRepository(path))
    expected = _session()
    first.save(expected)
    restarted = InMemorySessionRepository(JsonSessionRepository(path))
    assert restarted.get(SESSION_ID) == expected
    assert restarted.recovery_error is None


def test_session_document_is_versioned_and_written_atomically(tmp_path):
    path = tmp_path / "sessions.json"
    JsonSessionRepository(path).save_all((_session(),))
    raw = path.read_text(encoding="utf-8")
    assert '"schema_version": 1' in raw
    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupt_session_file_is_isolated_and_never_overwritten(tmp_path):
    path = tmp_path / "sessions.json"
    original = b"{invalid"
    path.write_bytes(original)
    repository = InMemorySessionRepository(JsonSessionRepository(path))
    assert repository.recovery_error == "SESSION_RECOVERY_FILE_INVALID"
    with pytest.raises(RecoveryFileInvalidError, match="refusing"):
        repository.save(_session())
    assert path.read_bytes() == original
