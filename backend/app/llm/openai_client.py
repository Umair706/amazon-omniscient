"""OpenAI / OpenAI-compatible LLM client (optional provider)."""

from openai import AsyncOpenAI, BadRequestError

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient, build_response_format


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
        json_mode: bool = False,
        response_schema: dict | None = None,
    ) -> str:
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})

            response_format = build_response_format(json_mode, response_schema)
            response = await self._create(messages, max_tokens, temperature, response_format)
            content = response.choices[0].message.content
            if content is None:
                raise LLMError("OpenAI returned empty response")
            return content
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"OpenAI API call failed: {e}") from e

    async def _create(self, messages, max_tokens, temperature, response_format):
        """Call the chat API, degrading the JSON request if the endpoint rejects it.

        Not every OpenAI-compatible server (older Ollama, some local runtimes)
        supports json_schema, or even json_object. So we try what was asked,
        then step down: json_schema -> json_object -> plain, rather than fail.
        """
        base = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format is None:
            return await self.client.chat.completions.create(**base)
        try:
            return await self.client.chat.completions.create(response_format=response_format, **base)
        except BadRequestError:
            if response_format.get("type") == "json_schema":
                try:
                    return await self.client.chat.completions.create(
                        response_format={"type": "json_object"}, **base
                    )
                except BadRequestError:
                    return await self.client.chat.completions.create(**base)
            return await self.client.chat.completions.create(**base)
