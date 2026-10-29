import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from companion.llm import stream_reply
from companion.schema import new_session


def test_real_adapter_against_local_sse_stub(monkeypatch):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for choices in ([], [{"index": 0, "delta": {"content": "你好"}}],
                            [{"index": 0, "delta": {"content": "，朋友"}}]):
                event = {"id": "test", "object": "chat.completion.chunk", "created": 0,
                         "model": "test-model", "choices": choices}
                self.wfile.write(("data: " + json.dumps(event) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
        monkeypatch.setenv("LLM_MODEL", "test-model")
        monkeypatch.setenv("LLM_API_KEY", "local-test")
        session = new_session()
        session["messages"] = [{"role": "user", "content": "你好"}]
        assert "".join(stream_reply(session, "live")) == "你好，朋友"
        assert received[0]["stream"] is True
        assert received[0]["messages"][0]["role"] == "system"
        assert received[0]["messages"][-1] == session["messages"][-1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
