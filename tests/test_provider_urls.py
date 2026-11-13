import httpx
import pytest

from schedule_solver.providers import OpenAINarrator


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:80@attacker.test/v1",
        "https://",
        "https://user:pass@example.test/v1",
        "http://example.test/v1",
        "https://example.test/v1?token=secret",
    ],
)
def test_invalid_or_deceptive_provider_urls_are_rejected(url):
    with httpx.Client() as client, pytest.raises(ValueError, match="URL"):
        OpenAINarrator(url, "test-key", "model", client)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/v1",
        "http://localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
        "http://[::1]:8000/v1",
    ],
)
def test_https_and_loopback_http_provider_urls_are_accepted(url):
    with httpx.Client() as client:
        assert OpenAINarrator(url, "test-key", "model", client).base_url == url
