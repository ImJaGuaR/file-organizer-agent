from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import DEFAULT_MODEL
from .models import Classification, FileSignal

ALLOWED_CATEGORIES = {
    "Documents",
    "Images",
    "Code",
    "Data",
    "Archives",
    "Audio",
    "Videos",
    "Research",
    "Review",
}


@dataclass
class AILabeler:
    model: str = DEFAULT_MODEL
    enabled: bool = False
    provider: str = "openai"
    base_url: str | None = None
    timeout_seconds: int = 30

    @classmethod
    def from_environment(
        cls,
        model: str | None = None,
        enabled: bool = False,
        provider: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
    ) -> "AILabeler":
        selected_provider = (provider or os.getenv("AI_PROVIDER") or "openai").lower()
        selected_model = model or _default_model_for_provider(selected_provider)
        selected_base_url = base_url or _default_base_url_for_provider(selected_provider)
        selected_timeout = timeout_seconds or int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        return cls(
            model=selected_model,
            enabled=enabled,
            provider=selected_provider,
            base_url=selected_base_url,
            timeout_seconds=selected_timeout,
        )

    def classify(self, signal: FileSignal, rule_classification: Classification) -> Classification | None:
        if not self.enabled:
            return None
        if not _worth_ai_call(signal, rule_classification):
            return None

        prompt = _build_prompt(signal, rule_classification)
        if self.provider == "openai":
            return self._classify_openai(prompt, rule_classification)
        if self.provider == "openai-compatible":
            return self._classify_openai_compatible(prompt, rule_classification)
        if self.provider == "ollama":
            return self._classify_ollama(prompt, rule_classification)

        return _unavailable(
            rule_classification,
            f"Unknown AI provider '{self.provider}'; used rule classification.",
        )

    def _classify_openai(self, prompt: str, rule_classification: Classification) -> Classification:
        if not os.getenv("OPENAI_API_KEY"):
            return _unavailable(
                rule_classification,
                "AI requested, but OPENAI_API_KEY is not set; used rule classification.",
            )
        try:
            from openai import OpenAI
        except ImportError:
            return _unavailable(
                rule_classification,
                "AI requested, but the openai package is not installed; used rule classification.",
            )

        client = OpenAI()
        try:
            response = client.responses.create(
                model=self.model,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "file_label",
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "category": {"type": "string", "enum": sorted(ALLOWED_CATEGORIES)},
                                "subfolder": {"type": ["string", "null"]},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "summary": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["category", "subfolder", "confidence", "summary", "reason"],
                        },
                        "strict": True,
                    }
                },
            )
        except Exception as exc:
            return _error(rule_classification, f"OpenAI request failed: {exc}")

        return _parse_response_text(
            getattr(response, "output_text", None),
            rule_classification,
            source="ai-openai",
        )

    def _classify_openai_compatible(self, prompt: str, rule_classification: Classification) -> Classification:
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        if not api_key:
            return _unavailable(
                rule_classification,
                "AI requested, but OPENAI_COMPATIBLE_API_KEY is not set; used rule classification.",
            )
        if not self.base_url:
            return _unavailable(
                rule_classification,
                "AI requested, but OPENAI_COMPATIBLE_BASE_URL is not set; used rule classification.",
            )

        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON for the file label. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 180,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "file_label",
                    "schema": _label_schema(),
                },
            },
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            try:
                data = _post_json(url, payload, headers, timeout_seconds=self.timeout_seconds)
            except HTTPError as exc:
                if exc.code != 400:
                    raise
                fallback_payload = dict(payload)
                fallback_payload.pop("response_format", None)
                data = _post_json(url, fallback_payload, headers, timeout_seconds=self.timeout_seconds)
            output_text = data["choices"][0]["message"]["content"]
        except (
            KeyError,
            IndexError,
            TypeError,
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            RemoteDisconnected,
        ) as exc:
            return _error(rule_classification, f"OpenAI-compatible request failed: {exc}")

        return _parse_response_text(output_text, rule_classification, source="ai-openai-compatible")

    def _classify_ollama(self, prompt: str, rule_classification: Classification) -> Classification:
        base_url = (self.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only valid JSON for the file label. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "options": {"num_predict": 400},
        }
        try:
            data = _post_json(
                f"{base_url}/api/chat",
                payload,
                {"Content-Type": "application/json"},
                timeout_seconds=self.timeout_seconds,
            )
            output_text = data["message"]["content"]
        except (KeyError, TypeError, HTTPError, URLError, TimeoutError) as exc:
            return _error(rule_classification, f"Ollama request failed: {exc}")

        return _parse_response_text(output_text, rule_classification, source="ai-ollama")


def _worth_ai_call(signal: FileSignal, rule_classification: Classification) -> bool:
    if signal.preview:
        return True
    return rule_classification.category in {"Research", "Review", "Documents", "Code", "Data"}


def _build_prompt(signal: FileSignal, rule_classification: Classification) -> str:
    preview = signal.preview[:1800] if signal.preview else "(No content preview available.)"
    return f"""
You are the GenAI labeling module for a File Organizer Agent.

Choose the best folder for the file. Return only JSON matching the schema.

Allowed top-level categories:
Documents, Images, Code, Data, Archives, Audio, Videos, Research, Review.

Use Review when uncertain. Prefer Research for academic papers, assignments,
milestones, literature reviews, citations, experiments, OS/coursework, or thesis work.

File metadata:
- name: {signal.name}
- extension: {signal.extension or "(none)"}
- mime_type: {signal.mime_type}
- size_bytes: {signal.size_bytes}
- rule_category: {rule_classification.category}
- rule_subfolder: {rule_classification.subfolder}
- rule_reason: {rule_classification.reason}

Content preview:
{preview}
""".strip()


def _label_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": {"type": "string", "enum": sorted(ALLOWED_CATEGORIES)},
            "subfolder": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["category", "subfolder", "confidence", "summary", "reason"],
    }


def _parse_response_text(output_text: str | None, fallback: Classification, source: str) -> Classification:
    if not output_text:
        return fallback
    output_text = _strip_markdown_fence(output_text)
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError:
        return fallback
    category = data.get("category")
    if category not in ALLOWED_CATEGORIES:
        return fallback
    subfolder = data.get("subfolder")
    if subfolder is not None:
        subfolder = str(subfolder).strip().strip("/\\") or None
    confidence = float(data.get("confidence", fallback.confidence))
    return Classification(
        category=category,
        subfolder=subfolder,
        confidence=max(0.0, min(1.0, confidence)),
        reason=str(data.get("reason", "AI suggested this category."))[:300],
        source=source,
        summary=str(data.get("summary", ""))[:240],
    )


def _default_model_for_provider(provider: str) -> str:
    if provider == "openai-compatible":
        return (
            os.getenv("OPENAI_COMPATIBLE_MODEL")
            or os.getenv("AI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or DEFAULT_MODEL
        )
    if provider == "ollama":
        return os.getenv("OLLAMA_MODEL") or os.getenv("AI_MODEL") or "llama3.1"
    return os.getenv("OPENAI_MODEL") or os.getenv("AI_MODEL") or DEFAULT_MODEL


def _default_base_url_for_provider(provider: str) -> str | None:
    if provider == "openai-compatible":
        return os.getenv("OPENAI_COMPATIBLE_BASE_URL")
    if provider == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return None


def _post_json(
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if detail:
            raise HTTPError(exc.url, exc.code, f"{exc.reason}: {detail}", exc.headers, exc.fp) from exc
        raise


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").strip()
        stripped = stripped.removesuffix("```").strip()
    return stripped


def _unavailable(fallback: Classification, reason: str) -> Classification:
    return Classification(
        category=fallback.category,
        subfolder=fallback.subfolder,
        confidence=fallback.confidence,
        reason=reason,
        source="ai-unavailable",
        summary=fallback.summary,
    )


def _error(fallback: Classification, reason: str) -> Classification:
    return Classification(
        category=fallback.category,
        subfolder=fallback.subfolder,
        confidence=fallback.confidence,
        reason=f"AI request failed; used rule classification. Error: {reason}",
        source="ai-error",
        summary=fallback.summary,
    )
