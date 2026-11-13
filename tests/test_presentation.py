import json

import httpx
import pytest

from schedule_solver.models import Explanation, Workload
from schedule_solver.providers import MockNarrator, OpenAINarrator
from schedule_solver.render import calendar_html
from schedule_solver.solver import solve


def test_html_escapes_ids_and_displays_local_time(payload):
    payload["requests"][0]["id"] = "<script>alert(1)</script>"
    work = Workload.model_validate(payload)
    html = calendar_html(work, solve(work))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "UTC" in html and "ada" in html and "calendar" in html


def test_mock_narrator_is_deterministic():
    explanation = Explanation(request_id="r", kind="insertion_conflict", facts=["Frozen schedule"], conflict=["cap:a:2027-01-04"], minimal=True)
    assert MockNarrator().describe(explanation) == MockNarrator().describe(explanation)
    assert "cap:a:" in MockNarrator().describe(explanation)


def test_openai_compatible_provider_uses_injected_boundary():
    def respond(request):
        assert request.url == "https://example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        certificate = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert certificate["conflict"] == []
        assert certificate["request_id"] == "r"
        return httpx.Response(200, json={"choices": [{"message": {"content": "Explanation."}}]})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAINarrator("https://example.test/v1", "test-key", "model", client)
        assert provider.describe(Explanation(request_id="r", kind="scheduled", facts=[])) == "Explanation."


def test_provider_errors_are_not_hidden():
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(429))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            OpenAINarrator("https://example.test", "key", "model", client).describe(Explanation(request_id="r", kind="scheduled", facts=[]))
