"""Qwen LLM client via DashScope OpenAI-compatible endpoint (DEFAULT provider)."""

from openai import AsyncOpenAI

from app.core.exceptions import LLMError
from app.llm.base_client import BaseLLMClient


class QwenClient(BaseLLMClient):
    """
    Qwen client using DashScope's OpenAI-compatible API.

    Default model: qwen-max-latest (best reasoning)
    Alternative: qwen-plus-latest (faster, cheaper)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-max-latest",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ):
        if not api_key:
            raise LLMError("DASHSCOPE_API_KEY is required for Qwen provider")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
                raise LLMError("Qwen returned empty response")
            return content
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Qwen API call failed: {e}") from e
