"""OpenAI / OpenAI-compatible LLM client (optional provider)."""

from openai import AsyncOpenAI

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """
    OpenAI client. Also works with any OpenAI-compatible API
    by setting a custom base_url (e.g., local models, Ollama, vLLM).

    Default model: gpt-4o
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ):
        if not api_key and not base_url:
            raise LLMError("OPENAI_API_KEY is required for OpenAI provider (or set OPENAI_BASE_URL for local models)")
        kwargs: dict = {"api_key": api_key or "not-needed"}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)
        self.model = model

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        system_message: str | None = None,
    ) -> str:
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content is None:
                raise LLMError("OpenAI returned empty response")
            return content
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI API call failed: {e}") from e
