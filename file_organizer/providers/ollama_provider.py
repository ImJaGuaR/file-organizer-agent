from __future__ import annotations

import os
from typing import Any

from .base import ProviderConfig, ProviderError
from .compatible_provider import _post_json, parse_json_object


class OllamaProvider:
    def __init__(self, config: ProviderConfig):
        self.config = ProviderConfig(
            provider="ollama",
            model=config.model or os.getenv("OLLAMA_MODEL") or os.getenv("AI_MODEL") or "llama3.1",
            base_url=config.base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434",
            timeout_seconds=config.timeout_seconds,
            retries=config.retries,
        )

    def auth_status(self) -> dict[str, str]:
        return {
            "provider": self.config.provider,
            "model": self.config.model or "",
            "base_url": self.config.base_url or "",
            "API key": "not required",
        }

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        try:
            data = _post_json(
                self.config.base_url.rstrip("/") + "/api/chat",
                payload,
                {"Content-Type": "application/json"},
                self.config.timeout_seconds,
            )
            return parse_json_object(data["message"]["content"])
        except Exception as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc

