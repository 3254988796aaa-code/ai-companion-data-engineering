import json

import pytest

from companion.schema import new_session
from companion.storage import SessionStore


def test_roundtrip_delete_and_atomic_cleanup(tmp_path):
    store = SessionStore(tmp_path)
    session = new_session()
    session["messages"] = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
    store.save(session)
    assert store.load(session["session_id"]) == session
    assert store.list_ids() == [session["session_id"]]
    assert not list(tmp_path.glob("*.tmp"))
    store.delete(session["session_id"])
    assert store.list_ids() == []


def test_load_legacy_format_and_reject_mismatched_id(tmp_path):
    store = SessionStore(tmp_path)
    raw = {"current_session": "legacy", "nick_name": "小爱", "nature": "活泼", "message": []}
    (tmp_path / "legacy.json").write_text(json.dumps(raw), encoding="utf-8")
    assert store.load("legacy")["nickname"] == "小爱"
    (tmp_path / "other.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        store.load("other")


@pytest.mark.parametrize("bad", ["../outside", "..\\outside", "/absolute", "", "a/b"])
def test_reject_path_traversal(tmp_path, bad):
    with pytest.raises(ValueError):
        SessionStore(tmp_path).delete(bad)
