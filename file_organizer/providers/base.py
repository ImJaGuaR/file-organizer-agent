from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Base provider failure."""


class ProviderUnavailable(ProviderError):
    """Raised when the selected provider is not configured or reachable."""


class StructuredOutputError(ProviderError):
    """Raised when a provider cannot return parseable structured data."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "openai"
    model: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 30
    retries: int = 1


class AIProvider(Protocol):
    config: ProviderConfig

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        """Return a JSON-compatible object matching the requested schema."""

    def auth_status(self) -> dict[str, str]:
        """Return non-secret provider configuration status."""

