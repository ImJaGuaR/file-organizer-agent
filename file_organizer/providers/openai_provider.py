from __future__ import annotations

import os
from typing import Any

from .base import ProviderConfig, ProviderUnavailable, StructuredOutputError


class OpenAIProvider:
    def __init__(self, config: ProviderConfig):
        model = config.model or os.getenv("OPENAI_MODEL") or os.getenv("AI_MODEL") or "gpt-5.4-mini"
        self.config = ProviderConfig(
            provider="openai",
            model=model,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            retries=config.retries,
        )

    def auth_status(self) -> dict[str, str]:
        return {
            "provider": self.config.provider,
            "model": self.config.model or "",
            "OPENAI_API_KEY": "set" if os.getenv("OPENAI_API_KEY") else "not set",
        }

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        if not os.getenv("OPENAI_API_KEY"):
            raise ProviderUnavailable("AI provider unavailable: OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailable("AI provider unavailable: openai package is not installed.") from exc

        client = OpenAI(timeout=self.config.timeout_seconds)
        response = client.responses.create(
            model=self.config.model,
            input=messages,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        output = getattr(response, "output_parsed", None)
        if isinstance(output, dict):
            return output
        text = getattr(response, "output_text", None)
        if not text:
            raise StructuredOutputError("OpenAI response did not include structured JSON.")
        from .compatible_provider import parse_json_object

        return parse_json_object(text)

