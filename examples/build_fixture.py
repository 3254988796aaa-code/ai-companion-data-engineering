"""Generate small, entirely synthetic fixtures. Never reads user conversations."""

import json
from pathlib import Path


def build_fixture(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = {"schema_version": 1, "session_id": "synthetic_01", "nickname": "小爱",
            "personality": "认真、耐心", "source_mode": "synthetic", "messages": [
                {"role": "user", "content": "我的演示邮箱是 learner@example.com，演示号码13800000000。"},
                {"role": "assistant", "content": "收到，我们可以用匿名信息继续练习。"},
                {"role": "user", "content": "请给我一个SQL练习。"},
                {"role": "assistant", "content": "可以先练习按订单状态分组计数。"}]}
    cases = {"01_valid": base,
             "02_duplicate": {**base, "session_id": "duplicate_with_another_id"},
             "03_empty": {**base, "session_id": "empty", "messages": []},
             "04_bad_role": {**base, "session_id": "bad_role", "messages": [
                 {"role": "assistant", "content": "错误的起始角色。"}]},
             "05_incomplete": {**base, "session_id": "incomplete", "messages": base["messages"][:1]},
             "06_demo": {**base, "session_id": "offline_demo", "source_mode": "demo"},
             "07_legacy": {"current_session": "2026-03-01_21-37-34", "nick_name": "小爱",
                 "nature": "活泼、认真", "message": [
                     {"role": "user", "content": "这是人工编写的旧格式样例，我想练习Python。"},
                     {"role": "assistant", "content": "可以从读取并汇总CSV数据开始。"}]}}
    for name, record in cases.items():
        (directory / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "08_invalid_json.json").write_text('{"synthetic_broken":', encoding="utf-8")


if __name__ == "__main__":
    build_fixture(Path(__file__).resolve().parent / "sessions")
