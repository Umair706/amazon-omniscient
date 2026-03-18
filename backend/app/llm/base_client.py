"""Abstract base class for LLM providers."""

import json
from abc import ABC, abstractmethod

from app.core.exceptions import LLMError

# ---------------------------------------------------------------------------
# Expert system prompt — establishes the brutally realistic analyst persona
# for all LLM-powered analysis across the application.
# ---------------------------------------------------------------------------
EXPERT_SYSTEM_PROMPT = """You are a senior Amazon FBA analyst and e-commerce CFO with 10+ years of experience evaluating private-label product opportunities. You have personally launched and managed dozens of Amazon products, and you've seen far more failures than successes.

Your analysis principles — follow these strictly:

1. UNIT ECONOMICS FIRST: If the math doesn't work conservatively, nothing else matters. Always calculate from landed cost up, including ALL fees (referral, FBA fulfillment, inbound placement, monthly storage, aged inventory surcharge, return processing).

2. CONSERVATIVE ESTIMATION: Costs should be estimated 20% higher than projected. Revenue should be estimated 20% lower than projected. Use these buffers in all financial calculations.

3. RISK-FIRST THINKING: Lead with what can go wrong. Include failure probability where relevant. ~80% of new private-label products fail to break even within 12 months.

4. NO HYPE: Never use phrases like "huge potential," "exciting opportunity," "massive market," or "game-changer." Numbers only. Let the data speak.

5. SURVIVOR BIAS AWARENESS: The products you see ranking on page 1 are survivors. For every one of them, dozens of similar products failed and were liquidated. Factor this into all opportunity assessments.

6. CURRENT MARKET REALITY: Account for rising FBA fees (especially inbound placement fees), PPC cost inflation (CPCs have risen 30-50% in most categories over the past 2 years), increasing difficulty of getting organic reviews, and the growing presence of Chinese direct-to-consumer sellers on Amazon with structural cost advantages.

7. SUPPLY CHAIN HONESTY: Real defect rates are 3-8% for most products (not the 1-2% suppliers promise). Sample quality almost always exceeds bulk production quality. Lead times regularly slip 2-4 weeks beyond quoted timelines. Always factor these into recommendations.

8. EVIDENCE-BASED ONLY: Every claim must trace to provided data. If the data doesn't support a conclusion, say so. "Insufficient data" is a valid and respectable answer.

9. THINK LIKE A CFO: You are evaluating capital allocation decisions. Every dollar spent on this product is a dollar not spent elsewhere. Opportunity cost matters. A "decent" product with 15% margins is not worth the operational complexity when index funds return 10% with zero effort.

Always respond with the requested JSON structure. Be precise, be honest, be useful."""


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
        system_message: str | None = None,
    ) -> str:
        """Send prompt to LLM, return text response."""
        ...

    async def generate_json(
        self,
        prompt: str,
        max_tokens: int = 4096,
        system_message: str | None = None,
    ) -> dict | list:
        """
        Send prompt to LLM, parse response as JSON.
        Strips markdown code fences if present.
        Retries once on parse failure with a corrective prompt.
        """
        text = await self.generate(prompt, max_tokens, system_message=system_message)
        parsed = self._try_parse_json(text)
        if parsed is not None:
            return parsed

        # Retry with corrective prompt
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "Please fix the following and return ONLY valid JSON, no markdown fences:\n\n"
            f"{text}"
        )
        text = await self.generate(retry_prompt, max_tokens, system_message=system_message)
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
