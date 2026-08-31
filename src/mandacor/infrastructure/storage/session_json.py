from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

from mandacor.domain.sessions import ColorSession, SessionState
from mandacor.infrastructure.storage.pending_adjustment_json import (
    RecoveryFileInvalidError,
    _measurement_from_dict,
    _measurement_to_dict,
)


SESSION_SCHEMA_VERSION = 1


def session_to_dict(session: ColorSession) -> dict[str, object]:
    return {
        "session_id": str(session.session_id),
        "created_at": session.created_at.isoformat(),
        "instrument_serial": session.instrument_serial,
        "state": session.state.value,
        "target": _measurement_to_dict(session.target) if session.target else None,
        "sample": _measurement_to_dict(session.sample) if session.sample else None,
    }


def session_from_dict(document: dict[str, object]) -> ColorSession:
    target = document.get("target")
    sample = document.get("sample")
    return ColorSession(
        session_id=uuid.UUID(str(document["session_id"])),
        created_at=datetime.fromisoformat(str(document["created_at"])),
        instrument_serial=document.get("instrument_serial"),
        target=_measurement_from_dict(target) if isinstance(target, dict) else None,
        sample=_measurement_from_dict(sample) if isinstance(sample, dict) else None,
        state=SessionState(str(document["state"])),
    )


class JsonSessionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def load_all(self) -> tuple[ColorSession, ...]:
        with self._lock:
            if not self.path.exists():
                return ()
            try:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                if document.get("schema_version") != SESSION_SCHEMA_VERSION:
                    raise ValueError("unsupported session recovery schema version")
                values = document["sessions"]
                if not isinstance(values, list):
                    raise ValueError("sessions must be an array")
                return tuple(session_from_dict(item) for item in values)
            except (OSError, ValueError, TypeError, KeyError) as error:
                raise RecoveryFileInvalidError(
                    f"session recovery file is invalid: {self.path}"
                ) from error

    def save_all(self, sessions: tuple[ColorSession, ...]) -> None:
        document = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "sessions": [session_to_dict(item) for item in sessions],
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(document, stream, indent=2, sort_keys=True)
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
