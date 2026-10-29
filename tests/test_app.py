from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"


def test_demo_chat_new_load_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COMPANION_MODE", "demo")
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    assert not app.exception
    app.chat_input[0].set_value("我想学SQL").run()
    assert not app.exception
    assert len(app.chat_message) == 2
    original = app.session_state["conversation"]["session_id"]
    assert (tmp_path / f"{original}.json").exists()
    app.button(key="new_session").click().run()
    assert not app.session_state["conversation"]["messages"]
    app.button(key=f"load_{original}").click().run()
    assert len(app.session_state["conversation"]["messages"]) == 2
    app.button(key=f"delete_{original}").click().run()
    assert not (tmp_path / f"{original}.json").exists()
    assert not app.session_state["conversation"]["messages"]
    assert not app.exception


def test_failed_stream_does_not_save_incomplete_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANION_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("COMPANION_MODE", "demo")

    def fail(*args, **kwargs):
        yield "partial"
        raise ConnectionError("simulated transport failure")

    monkeypatch.setattr("companion.llm.stream_reply", fail)
    app = AppTest.from_file(str(APP), default_timeout=15).run()
    app.chat_input[0].set_value("hello").run()
    assert not app.exception
    assert app.error
    assert not app.session_state["conversation"]["messages"]
    assert not list(tmp_path.glob("*.json"))
