"""Abstract base class for LLM providers."""

import json
from abc import ABC, abstractmethod

from app.core.exceptions import LLMError


class BaseLLMClient(ABC):
    """
    Abstract base class for all LLM providers.
    Every provider must implement the `generate` method.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Send prompt to LLM, return text response."""
        ...

    async def generate_json(
        self,
        prompt: str,
        max_tokens: int = 4096,
    ) -> dict | list:
        """
        Send prompt to LLM, parse response as JSON.
        Strips markdown code fences if present.
        Retries once on parse failure with a corrective prompt.
        """
        text = await self.generate(prompt, max_tokens)
        parsed = self._try_parse_json(text)
        if parsed is not None:
            return parsed

        # Retry with corrective prompt
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "Please fix the following and return ONLY valid JSON, no markdown fences:\n\n"
            f"{text}"
        )
        text = await self.generate(retry_prompt, max_tokens)
        parsed = self._try_parse_json(text)
        if parsed is not None:
            return parsed

        raise LLMError(f"Failed to parse LLM response as JSON after retry: {text[:200]}")

    @staticmethod
    def _try_parse_json(text: str) -> dict | list | None:
        """Attempt to parse text as JSON, stripping code fences if needed."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
