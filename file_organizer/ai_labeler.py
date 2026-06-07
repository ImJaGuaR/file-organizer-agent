from __future__ import annotations

import json
import os
from dataclasses import dataclass

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

    @classmethod
    def from_environment(cls, model: str | None = None, enabled: bool = False) -> "AILabeler":
        return cls(model=model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL), enabled=enabled)

    def classify(self, signal: FileSignal, rule_classification: Classification) -> Classification | None:
        if not self.enabled:
            return None
        if not os.getenv("OPENAI_API_KEY"):
            return Classification(
                category=rule_classification.category,
                subfolder=rule_classification.subfolder,
                confidence=rule_classification.confidence,
                reason="AI requested, but OPENAI_API_KEY is not set; used rule classification.",
                source="ai-unavailable",
                summary=rule_classification.summary,
            )
        if not _worth_ai_call(signal, rule_classification):
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return Classification(
                category=rule_classification.category,
                subfolder=rule_classification.subfolder,
                confidence=rule_classification.confidence,
                reason="AI requested, but the openai package is not installed; used rule classification.",
                source="ai-unavailable",
            )

        client = OpenAI()
        prompt = _build_prompt(signal, rule_classification)
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
            return Classification(
                category=rule_classification.category,
                subfolder=rule_classification.subfolder,
                confidence=rule_classification.confidence,
                reason=f"AI request failed; used rule classification. Error: {exc}",
                source="ai-error",
            )

        return _parse_response(response, rule_classification)


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


def _parse_response(response: object, fallback: Classification) -> Classification:
    output_text = getattr(response, "output_text", None)
    if not output_text:
        return fallback
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
        reason=str(data.get("reason", "AI suggested this category.")),
        source="ai",
        summary=str(data.get("summary", ""))[:500],
    )
