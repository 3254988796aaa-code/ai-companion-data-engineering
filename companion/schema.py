"""Normalize the original prototype's JSON and the current schema."""

import re
from uuid import uuid4


def new_session(nickname="小爱", personality="温柔、认真、善于倾听"):
    return {"schema_version": 1, "session_id": uuid4().hex,
            "nickname": nickname, "personality": personality, "messages": [], "source_mode": "unknown"}


def normalize_session(raw):
    if not isinstance(raw, dict):
        raise ValueError("session_not_object")
    if raw.get("schema_version", 1) != 1:
        raise ValueError("unsupported_schema_version")
    source_mode = raw.get("source_mode", "unknown")
    if source_mode not in ("unknown", "demo", "live", "synthetic"):
        raise ValueError("invalid_source_mode")
    session_id = raw.get("session_id", raw.get("current_session"))
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id):
        raise ValueError("invalid_session_id")
    nickname = raw.get("nickname", raw.get("nick_name", "小爱"))
    personality = raw.get("personality", raw.get("nature", "温柔、认真、善于倾听"))
    if not all(isinstance(s, str) and s.strip() for s in (nickname, personality)):
        raise ValueError("invalid_persona")
    messages = raw.get("messages", raw.get("message"))
    if not isinstance(messages, list):
        raise ValueError("messages_not_list")
    result = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError("message_not_object")
        role, content = message.get("role"), message.get("content")
        if role != ("user" if index % 2 == 0 else "assistant"):
            raise ValueError("invalid_role_order")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty_message")
        result.append({"role": role, "content": content.strip()})
    return {"schema_version": 1, "session_id": session_id,
            "nickname": nickname.strip(), "personality": personality.strip(),
            "messages": result, "source_mode": source_mode}


def system_prompt(session):
    return (f"你是名为{session['nickname']}的虚构AI伴侣角色。"
            f"性格：{session['personality']}。使用用户的语言，友善、简洁地回应。")
