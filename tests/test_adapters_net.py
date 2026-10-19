import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from caterya import AssuranceEngine, SystemConfig
from caterya.adapters.hosted import AnthropicAdapter, OpenAICompatAdapter
from caterya.adapters.net import check_url
from caterya.core.errors import PolicyViolation

SEEN = []


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.path.endswith("/chat/completions"):
            text = json.dumps(body)
            reply = "I can't help with that request." if "explosive" in text else "APPROVE" if "APPROVE or DENY" in text else "ok answer"
            out = {"choices": [{"message": {"content": reply}}]}
        else:
            out = {"content": [{"type": "text", "text": "claude says hi"}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    SEEN.clear()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_egress_controls(monkeypatch):
    with pytest.raises(PolicyViolation):
        check_url("http://example.com/x")  # plain http not allowed
    with pytest.raises(PolicyViolation):
        check_url("https://127.0.0.1/x")  # loopback is not public
    with pytest.raises(PolicyViolation):
        check_url("https://10.0.0.5/x")  # private range
    with pytest.raises(PolicyViolation):
        check_url("ftp://example.com/x")
    check_url("http://127.0.0.1:8080/x", allow_local=True)  # explicit opt-in for local model servers
    monkeypatch.setenv("CATERYA_ALLOWED_HOSTS", "api.openai.com")
    with pytest.raises(PolicyViolation):
        check_url("https://evil.example/x", allow_local=True)


def test_openai_compatible_adapter_against_local_server(server, monkeypatch):
    monkeypatch.setenv("FAKE_KEY", "k-123")
    ad = OpenAICompatAdapter("m1", base_url=server, api_key_env="FAKE_KEY", allow_local=True)
    assert ad.generate("hello", system="be brief", seed=3) == "ok answer"
    path, headers, body = SEEN[-1]
    assert path == "/chat/completions" and headers["authorization"] == "Bearer k-123" and body["seed"] == 3
    assert body["messages"][0] == {"role": "system", "content": "be brief"} and body["temperature"] == 0.0


def test_anthropic_adapter_request_shape(server, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    ad = AnthropicAdapter(model="some-model-id", base_url=server, allow_local=True)
    assert ad.generate("hi", system="sys") == "claude says hi"
    path, headers, body = SEEN[-1]
    assert path == "/v1/messages" and headers["x-api-key"] == "sk-test" and headers["anthropic-version"] == "2023-06-01"
    assert body["model"] == "some-model-id" and body["system"] == "sys" and body["messages"] == [{"role": "user", "content": "hi"}]
    with pytest.raises(ValueError):
        AnthropicAdapter()  # model must be chosen explicitly (no hard-coded default)


def test_hosted_adapter_plugs_into_engine(server):
    ad = OpenAICompatAdapter("m1", base_url=server, allow_local=True)
    rep = AssuranceEngine(SystemConfig("remote", "1", owner="o", intended_use="u", description="d", model_id="m1")).evaluate(ad, profile="CATERYA-FAIRNESS")
    o = {x.metric_id: x for x in rep.outcomes}
    assert o["counterfactual_parity_v1"].result.tested  # the metric ran against a real HTTP model server
