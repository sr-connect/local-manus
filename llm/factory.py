"""Build the correct LLM provider from config."""
from __future__ import annotations
from .base import BaseLLMProvider


def create_provider(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseLLMProvider:
    """
    provider: "ollama" | "openai" | "anthropic"
    Falls back to values in config if args are not given.
    """
    import config

    provider = provider.lower()

    if provider == "ollama":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(
            model=model or config.OLLAMA_MODEL,
            api_key="ollama",
            base_url=base_url or config.OLLAMA_BASE_URL,
        )

    if provider == "openai":
        from .openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(
            model=model or config.OPENAI_MODEL,
            api_key=api_key or config.OPENAI_API_KEY,
        )

    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            model=model or config.ANTHROPIC_MODEL,
            api_key=api_key or config.ANTHROPIC_API_KEY,
        )

    raise ValueError(f"Unknown provider: {provider!r}. Choose ollama | openai | anthropic")
