"""Atomic local JSON storage; IDs cannot escape the storage directory."""

import json
import os
import re
import tempfile
from pathlib import Path

from companion.schema import normalize_session


class SessionStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id):
            raise ValueError("invalid_session_id")
        return self.directory / f"{session_id}.json"

    def save(self, session):
        normalized = normalize_session(session)
        target = self._path(normalized["session_id"])
        handle, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(normalized, stream, ensure_ascii=False, indent=2)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self, session_id):
        with self._path(session_id).open(encoding="utf-8-sig") as stream:
            session = normalize_session(json.load(stream))
        if session["session_id"] != session_id:
            raise ValueError("session_id_mismatch")
        return session

    def list_ids(self):
        return [p.stem for p in sorted(self.directory.glob("*.json"),
                key=lambda p: p.stat().st_mtime_ns, reverse=True)]

    def delete(self, session_id):
        self._path(session_id).unlink(missing_ok=True)
