from __future__ import annotations

from .base import ProviderConfig, ProviderError, ProviderUnavailable, StructuredOutputError
from .compatible_provider import OpenAICompatibleProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def create_provider(config: ProviderConfig):
    provider = config.provider.lower()
    if provider == "openai":
        return OpenAIProvider(config)
    if provider == "openai-compatible":
        return OpenAICompatibleProvider(config)
    if provider == "ollama":
        return OllamaProvider(config)
    raise ProviderUnavailable(f"Unknown AI provider '{config.provider}'.")


__all__ = [
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "ProviderConfig",
    "ProviderError",
    "ProviderUnavailable",
    "StructuredOutputError",
    "create_provider",
]

