"""LLM client factory — reads LLM_PROVIDER config and returns the correct client."""

from app.llm.base_client import BaseLLMClient


def create_llm_client(settings) -> BaseLLMClient:
    """
    Factory function: creates the appropriate LLM client based on settings.

    LLM_PROVIDER=qwen      -> QwenClient (DEFAULT)
    LLM_PROVIDER=anthropic  -> AnthropicClient
    LLM_PROVIDER=openai     -> OpenAIClient
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "qwen":
        from app.llm.qwen_client import QwenClient

        return QwenClient(
            api_key=settings.DASHSCOPE_API_KEY,
            model=settings.LLM_MODEL or "qwen-max-latest",
            base_url=settings.QWEN_BASE_URL,
        )

    elif provider == "anthropic":
        from app.llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL or "claude-sonnet-4-20250514",
        )

    elif provider == "openai":
        from app.llm.openai_client import OpenAIClient

        return OpenAIClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL or "gpt-4o",
            base_url=settings.OPENAI_BASE_URL or None,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported providers: qwen, anthropic, openai"
        )
