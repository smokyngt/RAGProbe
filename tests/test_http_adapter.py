import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from ragbench.config import PipelineConfig
from ragbench.pipelines import HTTPPipelineAdapter, PipelineError


@pytest.fixture
def server():
    """Serveur dont le comportement est un script de réponses : [(status, body|callable), ...]."""
    state = {"script": [], "hits": 0}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            i = min(state["hits"], len(state["script"]) - 1)
            state["hits"] += 1
            status, body = state["script"][i]
            if callable(body):
                body()
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_port}/query"
    yield state
    srv.shutdown()


def adapter(url, **kw):
    return HTTPPipelineAdapter(PipelineConfig(name="t", endpoint=url, retry_backoff_s=0, **kw))


OK = {"answer": "42", "retrieved_chunks": ["a", {"id": "b", "content": "texte", "score": 0.5}]}


def test_success_parses_str_and_object_chunks(server):
    server["script"] = [(200, OK)]
    r = adapter(server["url"]).query("q")
    assert r.answer == "42" and r.latency_ms > 0
    assert [c.chunk_id for c in r.retrieved_chunks] == ["a", "b"]
    assert r.retrieved_chunks[1].text == "texte" and r.retrieved_chunks[1].score == 0.5


def test_retries_on_5xx_then_succeeds(server):
    server["script"] = [(503, {}), (500, {}), (200, OK)]
    assert adapter(server["url"], max_retries=2).query("q").answer == "42"
    assert server["hits"] == 3


def test_gives_up_after_max_retries(server):
    server["script"] = [(500, {})]
    with pytest.raises(PipelineError, match="3 tentatives"):
        adapter(server["url"], max_retries=2).query("q")
    assert server["hits"] == 3


def test_no_retry_on_4xx(server):
    server["script"] = [(400, {"error": "bad"})]
    with pytest.raises(PipelineError, match="HTTP 400"):
        adapter(server["url"], max_retries=3).query("q")
    assert server["hits"] == 1


@pytest.mark.parametrize("body", [b"not json", {"answer": "x"}, {"answer": 1, "retrieved_chunks": []},
                                  {"answer": "x", "retrieved_chunks": [{"text": "no id"}]}])
def test_invalid_payload(server, body):
    server["script"] = [(200, body)]
    with pytest.raises(PipelineError):
        adapter(server["url"], max_retries=0).query("q")


def test_timeout_and_connection_refused(server):
    import time
    server["script"] = [(200, lambda: time.sleep(0.5))]
    with pytest.raises(PipelineError, match="Timeout"):
        adapter(server["url"], timeout=0.1, max_retries=0).query("q")
    with pytest.raises(PipelineError, match="ConnectionError"):
        adapter("http://127.0.0.1:9/query", max_retries=0).query("q")
