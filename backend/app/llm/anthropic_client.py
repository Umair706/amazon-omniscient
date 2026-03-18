"""Anthropic Claude LLM client (optional provider)."""

import anthropic

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient


class AnthropicClient(BaseLLMClient):
    """
    Anthropic Claude client.
    Default model: claude-sonnet-4-20250514
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
    ):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is required for Anthropic provider")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        system_message: str | None = None,
    ) -> str:
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_message:
                kwargs["system"] = system_message

            response = await self.client.messages.create(**kwargs)
            if not response.content:
                raise LLMError("Anthropic returned empty response")
            return response.content[0].text
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Anthropic API call failed: {e}") from e
