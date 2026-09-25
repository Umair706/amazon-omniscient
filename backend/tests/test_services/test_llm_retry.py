import httpx
import pytest

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient, _is_retryable


class FlakyClient(BaseLLMClient):
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def generate(self, prompt, max_tokens=4096, temperature=0.3, system_message=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("boom")
        return '{"ok": true}'


async def test_generate_json_retries_transport_errors(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    client = FlakyClient(failures=2)
    assert await client.generate_json("hi") == {"ok": True}
    assert client.calls == 3


async def test_generate_json_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    with pytest.raises(LLMError):
        await FlakyClient(failures=5).generate_json("hi")


def test_is_retryable_true_for_rate_limit_marker():
    assert _is_retryable(LLMError("rate limit exceeded")) is True


def test_is_retryable_false_for_json_parse_failure():
    assert _is_retryable(LLMError("Failed to parse LLM response")) is False
