import httpx
import openai
import pytest

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient, _is_retryable


class FlakyClient(BaseLLMClient):
    """Simulates a client whose transport raises raw httpx errors directly."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def generate(self, prompt, max_tokens=4096, temperature=0.3, system_message=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("boom")
        return '{"ok": true}'


class FlakyOpenAIWrappedClient(BaseLLMClient):
    """Simulates the real OpenAIClient/QwenClient shape: SDK timeouts get
    caught and re-raised as `LLMError(...) from e`, so callers only ever see
    a wrapped LLMError, never the raw openai exception."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def generate(self, prompt, max_tokens=4096, temperature=0.3, system_message=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise _wrapped_openai_timeout()
        return '{"ok": true}'


def _wrapped_openai_timeout() -> LLMError:
    """Build an LLMError the same way the concrete clients do when the
    OpenAI SDK times out: `raise LLMError(...) from e` sets __cause__ to the
    original openai.APITimeoutError."""
    cause = openai.APITimeoutError(request=httpx.Request("POST", "https://x"))
    try:
        raise LLMError("OpenAI API call failed: Request timed out.") from cause
    except LLMError as wrapped:
        return wrapped


async def test_generate_json_retries_transport_errors(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    client = FlakyClient(failures=2)
    assert await client.generate_json("hi") == {"ok": True}
    assert client.calls == 3


async def test_generate_json_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    with pytest.raises(LLMError):
        await FlakyClient(failures=5).generate_json("hi")


async def test_generate_json_retries_wrapped_openai_timeout(monkeypatch):
    """Regression: openai.APITimeoutError's message is the fixed string
    "Request timed out." with no "timeout" substring casing our old
    text-only matcher relied on. This must still retry via the __cause__
    type check, not just the message marker."""
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)
    client = FlakyOpenAIWrappedClient(failures=2)
    assert await client.generate_json("hi") == {"ok": True}
    assert client.calls == 3


def test_is_retryable_true_for_wrapped_openai_timeout_cause():
    assert _is_retryable(_wrapped_openai_timeout()) is True


def test_is_retryable_true_for_timed_out_marker_without_cause():
    # Same wording as the real openai.APITimeoutError message, but with no
    # __cause__ attached — must still match on the "timed out" text marker.
    assert _is_retryable(LLMError("Qwen API call failed: Request timed out.")) is True


def test_is_retryable_true_for_rate_limit_marker():
    assert _is_retryable(LLMError("rate limit exceeded")) is True


def test_is_retryable_false_for_json_parse_failure():
    assert _is_retryable(LLMError("Failed to parse LLM response as JSON after retry: ...")) is False


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://llm.example/v1/chat")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


@pytest.mark.parametrize("status_code, expected", [(401, False), (400, False), (429, True), (500, True), (503, True)])
def test_is_retryable_for_http_status_only_on_rate_limit_or_server_error(status_code, expected):
    assert _is_retryable(_http_status_error(status_code)) is expected


def test_wrapped_401_is_not_retried_even_though_its_text_looks_transient():
    try:
        raise LLMError("connection refused by gateway") from _http_status_error(401)
    except LLMError as wrapped:
        assert _is_retryable(wrapped) is False


async def test_generate_json_does_not_retry_a_bad_api_key(monkeypatch):
    monkeypatch.setattr("app.llm.base_client.RETRY_BACKOFF_SECONDS", 0)

    class UnauthorisedClient(BaseLLMClient):
        calls = 0

        async def generate(self, prompt, max_tokens=4096, temperature=0.3, system_message=None):
            self.calls += 1
            raise _http_status_error(401)

    client = UnauthorisedClient()
    with pytest.raises(httpx.HTTPStatusError):
        await client.generate_json("hi")
    assert client.calls == 1
