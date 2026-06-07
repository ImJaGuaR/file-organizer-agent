from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from http.client import RemoteDisconnected
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import DEFAULT_MODEL, PURPOSE_CATEGORIES
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
} | PURPOSE_CATEGORIES


@dataclass
class AILabeler:
    model: str = DEFAULT_MODEL
    enabled: bool = False
    provider: str = "openai"
    base_url: str | None = None
    timeout_seconds: int = 30
    scope: str = "smart"
    allow_custom_folders: bool = False

    @classmethod
    def from_environment(
        cls,
        model: str | None = None,
        enabled: bool = False,
        provider: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        scope: str | None = None,
        allow_custom_folders: bool = False,
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
            scope=scope or os.getenv("AI_SCOPE", "smart"),
            allow_custom_folders=allow_custom_folders,
        )

    def classify(self, signal: FileSignal, rule_classification: Classification) -> Classification | None:
        if not self.enabled:
            return None
        if not _worth_ai_call(signal, rule_classification, self.scope):
            return None

        prompt = _build_prompt(signal, rule_classification, self.allow_custom_folders)
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
                        "schema": _label_schema(self.allow_custom_folders),
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
            allow_custom_folders=self.allow_custom_folders,
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
            "max_tokens": 120,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "file_label",
                    "schema": _label_schema(self.allow_custom_folders),
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

        return _parse_response_text(
            output_text,
            rule_classification,
            source="ai-openai-compatible",
            allow_custom_folders=self.allow_custom_folders,
        )

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
            "options": {"num_predict": 120, "temperature": 0},
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

        return _parse_response_text(
            output_text,
            rule_classification,
            source="ai-ollama",
            allow_custom_folders=self.allow_custom_folders,
        )


def _worth_ai_call(signal: FileSignal, rule_classification: Classification, scope: str) -> bool:
    if scope == "all":
        return True
    if signal.preview:
        return True
    return rule_classification.category in {"Research", "Review", "Documents", "Code", "Data"}


def _build_prompt(
    signal: FileSignal,
    rule_classification: Classification,
    allow_custom_folders: bool,
) -> str:
    preview = signal.preview[:900] if signal.preview else "(No content preview available.)"
    custom_folder_instruction = (
        "You may create a new top-level category only when none of the allowed categories fit. "
        "Use safe folder names only."
        if allow_custom_folders
        else "Use only the allowed top-level categories."
    )
    return f"""
You are the GenAI labeling module for a File Organizer Agent.

Choose the best folder for the file. Return only JSON matching the schema.

Allowed top-level categories:
Documents, Images, Code, Data, Archives, Audio, Videos, Research, Review,
Ideas, Finance, Coursework, Meetings, Personal, Projects, Backups, Design.

Use Review when uncertain. Prefer Research for academic papers, assignments,
milestones, literature reviews, citations, experiments, OS/coursework, or thesis work.
{custom_folder_instruction}

Prefer PURPOSE over file type.
Use file type as the subfolder when purpose is known.
Examples:
- voice_memo_project_idea.m4a -> Ideas / Audio
- invoice_april_2026.pdf -> Finance / PDFs
- bank_statement_may.csv -> Finance / CSV
- meeting_notes_team_alpha.txt -> Meetings / Text
- lecture_slides_week_04.pptx -> Coursework / Presentations
- old_project_backup.tar.gz -> Backups / Archives
- system_architecture_diagram.svg -> Design / Diagrams

Write clean, short English:
- summary: max 12 words, no repeated words.
- reason: max 18 words, no repeated words.
- subfolder: short folder name or null.

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


def _label_schema(allow_custom_folders: bool) -> dict[str, object]:
    category_schema: dict[str, object] = {"type": "string"}
    if not allow_custom_folders:
        category_schema["enum"] = sorted(ALLOWED_CATEGORIES)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "category": category_schema,
            "subfolder": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["category", "subfolder", "confidence", "summary", "reason"],
    }


def _parse_response_text_with_options(
    output_text: str | None,
    fallback: Classification,
    source: str,
    allow_custom_folders: bool,
) -> Classification:
    if not output_text:
        return _fallback_after_ai(fallback, "AI returned no text; used rule classification.")
    output_text = _strip_markdown_fence(output_text)
    output_text = _extract_json_object(output_text)
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError:
        return _fallback_after_ai(fallback, "AI returned invalid JSON; used rule classification.")
    category = _sanitize_folder_part(str(data.get("category", "")))
    if category not in ALLOWED_CATEGORIES and not allow_custom_folders:
        return _fallback_after_ai(fallback, "AI returned an unsupported category; used rule classification.")
    if not category:
        return _fallback_after_ai(fallback, "AI returned an unsafe folder name; used rule classification.")
    subfolder = data.get("subfolder")
    if subfolder is not None:
        subfolder = _sanitize_folder_path(str(subfolder)) or None
    confidence = float(data.get("confidence", fallback.confidence))
    return Classification(
        category=category,
        subfolder=subfolder,
        confidence=max(0.0, min(1.0, confidence)),
        reason=_clean_ai_text(str(data.get("reason", "AI suggested this category.")), max_words=24),
        source=source,
        summary=_clean_ai_text(str(data.get("summary", "")), max_words=16),
    )


def _parse_response_text(
    output_text: str | None,
    fallback: Classification,
    source: str,
    allow_custom_folders: bool,
) -> Classification:
    return _parse_response_text_with_options(
        output_text,
        fallback,
        source,
        allow_custom_folders=allow_custom_folders,
    )


def _clean_ai_text(text: str, max_words: int) -> str:
    text = _strip_markdown_fence(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b(\w+)(?:\s+\1\b){2,}", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w{4,})(?:\1){1,}\b", r"\1", text, flags=re.IGNORECASE)
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]).rstrip(".,;:") + "."
    return text[:220]


def _sanitize_folder_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9 ._-]+", " ", value).strip(" ._-")
    value = re.sub(r"\s+", " ", value)
    if value in {"", ".", ".."}:
        return ""
    return value[:40]


def _sanitize_folder_path(value: str) -> str:
    parts = []
    for raw_part in re.split(r"[/\\]+", value):
        part = _sanitize_folder_part(raw_part)
        if part:
            parts.append(part)
        if len(parts) >= 3:
            break
    return "/".join(parts)


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


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
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


def _fallback_after_ai(fallback: Classification, reason: str) -> Classification:
    return Classification(
        category=fallback.category,
        subfolder=fallback.subfolder,
        confidence=fallback.confidence,
        reason=reason,
        source="ai-fallback",
        summary=fallback.summary,
    )
