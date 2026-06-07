from __future__ import annotations

from .config import (
    ARCHIVE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    CODE_EXTENSIONS,
    DATA_EXTENSIONS,
    DIAGRAM_KEYWORDS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    RESEARCH_KEYWORDS,
    SCREENSHOT_KEYWORDS,
    VIDEO_EXTENSIONS,
)
from .memory import OrganizerMemory
from .models import Classification, FileSignal


def classify_with_rules(signal: FileSignal, memory: OrganizerMemory | None = None) -> Classification:
    if memory:
        remembered = memory.classify_name(signal.name) or memory.classify_extension(signal.extension)
        if remembered:
            category, subfolder = remembered
            return Classification(
                category=category,
                subfolder=subfolder,
                confidence=0.98,
                reason="Matched saved memory rule.",
                source="memory",
            )

    text = f"{signal.name}\n{signal.preview}".lower()

    if _looks_research_related(text):
        return Classification(
            category="Research",
            subfolder=None,
            confidence=0.86,
            reason="File name or content contains academic/research keywords.",
        )

    if signal.extension in DOCUMENT_EXTENSIONS:
        category, subfolder = DOCUMENT_EXTENSIONS[signal.extension]
        return Classification(category, subfolder, 0.9, f"Matched document extension {signal.extension}.")

    if signal.extension in DATA_EXTENSIONS:
        category, subfolder = DATA_EXTENSIONS[signal.extension]
        return Classification(category, subfolder, 0.9, f"Matched data extension {signal.extension}.")

    if signal.extension in IMAGE_EXTENSIONS:
        subfolder = _image_subfolder(text)
        return Classification("Images", subfolder, 0.88, f"Matched image extension {signal.extension}.")

    if signal.extension in CODE_EXTENSIONS:
        return Classification("Code", _code_subfolder(signal.extension), 0.9, f"Matched code extension {signal.extension}.")

    if signal.extension in VIDEO_EXTENSIONS:
        return Classification("Videos", None, 0.9, f"Matched video extension {signal.extension}.")

    if signal.extension in AUDIO_EXTENSIONS:
        return Classification("Audio", None, 0.9, f"Matched audio extension {signal.extension}.")

    if signal.extension in ARCHIVE_EXTENSIONS:
        return Classification("Archives", None, 0.9, f"Matched archive extension {signal.extension}.")

    return Classification(
        category="Review",
        subfolder=None,
        confidence=0.25,
        reason="Unknown extension or insufficient metadata.",
    )


def choose_final_classification(
    rule_classification: Classification,
    ai_classification: Classification | None,
) -> Classification:
    if not ai_classification:
        return rule_classification
    if ai_classification.confidence >= 0.76:
        return ai_classification
    if rule_classification.category == "Review" and ai_classification.confidence >= 0.55:
        return ai_classification
    return rule_classification


def _looks_research_related(text: str) -> bool:
    return any(keyword in text for keyword in RESEARCH_KEYWORDS)


def _image_subfolder(text: str) -> str:
    if any(keyword in text for keyword in SCREENSHOT_KEYWORDS):
        return "Screenshots"
    if any(keyword in text for keyword in DIAGRAM_KEYWORDS):
        return "Diagrams"
    if any(word in text for word in {"photo", "img_", "dcim", "portrait"}):
        return "Photos"
    return "Other"


def _code_subfolder(extension: str) -> str | None:
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".jsx": "JavaScript",
        ".java": "Java",
        ".c": "C",
        ".cpp": "Cpp",
        ".cs": "CSharp",
        ".html": "Web",
        ".css": "Web",
        ".sql": "SQL",
        ".ipynb": "Notebooks",
    }
    return mapping.get(extension)
