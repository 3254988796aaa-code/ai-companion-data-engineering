import json

import pytest

from companion.pipeline import run_pipeline
from companion.schema import normalize_session
from examples.build_fixture import build_fixture


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_quality_fixture_and_reproducibility(tmp_path):
    source = tmp_path / "source"
    build_fixture(source)
    first, second = tmp_path / "first", tmp_path / "second"
    report = run_pipeline(source, first)
    assert report["input_files"] == 8
    assert report["accepted_sessions"] == 2
    assert report["rejected_files"] == 6
    assert report["rejection_reasons"] == {
        "duplicate_session": 1, "empty_session": 1, "invalid_role_order": 1,
        "incomplete_turn": 1, "demo_session": 1, "invalid_json": 1}
    assert report["redactions_in_accepted_sessions"]["email"] == 1
    assert report["redactions_in_accepted_sessions"]["phone"] == 1
    assert report["train_examples"] + report["eval_examples"] == 3
    assert report == run_pipeline(source, second)
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    output = (first / "sessions.jsonl").read_text(encoding="utf-8")
    assert "learner@example.com" not in output and "13800000000" not in output
    assert "[EMAIL]" in output and "[PHONE]" in output
    assert "synthetic_01" not in output
    train = read_jsonl(first / "sft_train.jsonl")
    evaluation = read_jsonl(first / "sft_eval.jsonl")
    assert not ({x["session_id"] for x in train} & {x["session_id"] for x in evaluation})
    assert all(x["messages"][0]["role"] == "system" and
               x["messages"][-1]["role"] == "assistant" for x in train + evaluation)


@pytest.mark.parametrize("percent", [0, 100])
def test_split_extremes_preserve_full_sessions(tmp_path, percent):
    build_fixture(tmp_path / "source")
    report = run_pipeline(tmp_path / "source", tmp_path / "out", percent)
    assert report["eval_examples" if percent == 100 else "train_examples"] == 3
    assert report["train_examples" if percent == 100 else "eval_examples"] == 0


@pytest.mark.parametrize("content,reason", [
    (None, "session_not_object"),
    ({"session_id": "../../escape", "messages": []}, "invalid_session_id"),
    ({"session_id": "ok", "nickname": 123, "messages": []}, "invalid_persona"),
    ({"session_id": "ok", "messages": "bad"}, "messages_not_list"),
    ({"session_id": "ok", "messages": ["bad"]}, "message_not_object"),
    ({"session_id": "ok", "messages": [{"role": "user", "content": " "}]}, "empty_message"),
    ({"schema_version": 2}, "unsupported_schema_version"),
    ({"source_mode": "untrusted"}, "invalid_source_mode"),
])
def test_invalid_schema(content, reason):
    with pytest.raises(ValueError, match=reason):
        normalize_session(content)


def test_sensitive_persona_and_key_redaction(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    record = {"session_id": "one", "nickname": "user@example.com", "personality": "13800000000",
              "messages": [{"role": "user", "content": "sk-" + "TESTONLY" * 4},
                           {"role": "assistant", "content": "你好"}]}
    (source / "one.json").write_text(json.dumps(record), encoding="utf-8")
    report = run_pipeline(source, tmp_path / "out")
    output = (tmp_path / "out" / "sessions.jsonl").read_text(encoding="utf-8")
    assert "TESTONLY" not in output and "user@example.com" not in output
    assert "13800000000" not in output
    assert report["redactions_in_accepted_sessions"] == {"api_key": 1, "email": 1, "phone": 1}


def test_missing_input_and_overlapping_output_fail(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        run_pipeline(tmp_path / "missing", tmp_path / "out")
    with pytest.raises(ValueError, match="separate"):
        run_pipeline(tmp_path, tmp_path / "out")
