from __future__ import annotations

import json
import os
from http.client import RemoteDisconnected
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ProviderConfig, ProviderError, ProviderUnavailable


class OpenAICompatibleProvider:
    def __init__(self, config: ProviderConfig):
        model = (
            config.model
            or os.getenv("OPENAI_COMPATIBLE_MODEL")
            or os.getenv("AI_MODEL")
            or "gpt-5.4-mini"
        )
        base_url = config.base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        self.config = ProviderConfig(
            provider="openai-compatible",
            model=model,
            base_url=base_url,
            timeout_seconds=config.timeout_seconds,
            retries=config.retries,
        )

    def auth_status(self) -> dict[str, str]:
        return {
            "provider": self.config.provider,
            "model": self.config.model or "",
            "base_url": self.config.base_url or "not set",
            "OPENAI_COMPATIBLE_API_KEY": "set" if os.getenv("OPENAI_COMPATIBLE_API_KEY") else "not set",
        }

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        if not api_key:
            raise ProviderUnavailable("AI provider unavailable: OPENAI_COMPATIBLE_API_KEY is not set.")
        if not self.config.base_url:
            raise ProviderUnavailable("AI provider unavailable: OPENAI_COMPATIBLE_BASE_URL is not set.")

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        try:
            try:
                data = _post_json(url, payload, headers, self.config.timeout_seconds)
            except HTTPError as exc:
                if exc.code != 400:
                    raise
                fallback = dict(payload)
                fallback.pop("response_format", None)
                data = _post_json(url, fallback, headers, self.config.timeout_seconds)
            return parse_json_object(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, HTTPError, URLError, TimeoutError, OSError, RemoteDisconnected) as exc:
            raise ProviderError(f"OpenAI-compatible request failed: {exc}") from exc


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Structured output must be a JSON object.")
    return parsed

