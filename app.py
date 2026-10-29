"""Run with: python -m streamlit run app.py"""

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from companion.llm import stream_reply
from companion.schema import new_session
from companion.storage import SessionStore

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="小爱 · AI智能伴侣", page_icon="💬", layout="wide")
data_dir = Path(os.environ.get("COMPANION_DATA_DIR", "data/sessions"))
store = SessionStore(data_dir if data_dir.is_absolute() else ROOT / data_dir)
if "conversation" not in st.session_state:
    st.session_state.conversation = new_session()
session = st.session_state.conversation

with st.sidebar:
    st.title("💬 小爱")
    mode = st.selectbox("对话模式", ["demo", "live"],
        index=0 if os.environ.get("COMPANION_MODE", "demo") == "demo" else 1,
        format_func=lambda x: "离线演示" if x == "demo" else "真实模型")
    st.caption("离线模式使用固定回复，无需模型或密钥。" if mode == "demo" else "使用 .env 中配置的模型服务。")
    if st.button("新建会话", key="new_session"):
        store.save(session)
        st.session_state.conversation = new_session(session["nickname"], session["personality"])
        st.rerun()
    with st.form("persona"):
        nickname = st.text_input("昵称", value=session["nickname"], max_chars=40)
        personality = st.text_area("性格", value=session["personality"], max_chars=500)
        if st.form_submit_button("保存角色设置"):
            if nickname.strip() and personality.strip():
                session.update(nickname=nickname.strip(), personality=personality.strip())
                store.save(session)
                st.rerun()
            else:
                st.error("请填写昵称和性格。")
    st.subheader("会话历史")
    for sid in store.list_ids():
        col1, col2 = st.columns([4, 1])
        if col1.button(sid[:18], key=f"load_{sid}"):
            try:
                loaded = store.load(sid)
                store.save(session)
                st.session_state.conversation = loaded
                st.rerun()
            except (ValueError, OSError):
                st.error("会话文件无法读取，请检查数据格式。")
        if col2.button("×", key=f"delete_{sid}", help="删除会话"):
            store.delete(sid)
            if session["session_id"] == sid:
                st.session_state.conversation = new_session()
            st.rerun()

st.title("AI 智能伴侣")
st.caption("自定义角色 · 流式对话 · 本地会话管理")
if not session["messages"]:
    st.info("在左侧设置角色，然后输入第一条消息。")
for message in session["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input("今天想聊些什么？", max_chars=4000)
if prompt:
    if session["messages"] and session["source_mode"] not in ("unknown", mode):
        st.warning("切换对话模式后，请先新建会话。")
        st.stop()
    previous = list(session["messages"])
    previous_mode = session["source_mode"]
    session["source_mode"] = mode
    session["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    try:
        with st.chat_message("assistant"):
            response = st.write_stream(stream_reply(session, mode))
        if not isinstance(response, str) or not response.strip():
            raise ValueError("empty_model_response")
        session["messages"].append({"role": "assistant", "content": response})
        store.save(session)
    except Exception:
        session["messages"] = previous
        session["source_mode"] = previous_mode
        st.error("本轮对话未保存。请检查模型服务、密钥或存储权限后重试。")

st.download_button("下载当前会话 JSON", json.dumps(session, ensure_ascii=False, indent=2),
                   file_name=f"{session['session_id']}.json", mime="application/json")
