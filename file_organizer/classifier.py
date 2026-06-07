from __future__ import annotations

from .config import (
    ARCHIVE_EXTENSIONS,
    AUDIO_EXTENSIONS,
    BACKUP_KEYWORDS,
    CODE_EXTENSIONS,
    COURSEWORK_KEYWORDS,
    DATA_EXTENSIONS,
    DIAGRAM_KEYWORDS,
    DOCUMENT_EXTENSIONS,
    FINANCE_KEYWORDS,
    IDEA_KEYWORDS,
    IMAGE_EXTENSIONS,
    MEETING_KEYWORDS,
    PERSONAL_KEYWORDS,
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

    purpose = _purpose_classification(signal, text)
    if purpose:
        return purpose

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
    prefer_ai: bool = False,
) -> Classification:
    if not ai_classification:
        return rule_classification
    if prefer_ai and ai_classification.source.startswith("ai-"):
        return ai_classification
    if ai_classification.confidence >= 0.76:
        return ai_classification
    if rule_classification.category == "Review" and ai_classification.confidence >= 0.55:
        return ai_classification
    return rule_classification


def _looks_research_related(text: str) -> bool:
    return any(keyword in text for keyword in RESEARCH_KEYWORDS)


def _purpose_classification(signal: FileSignal, text: str) -> Classification | None:
    type_folder = _type_folder_for_purpose(signal)
    if any(keyword in text for keyword in IDEA_KEYWORDS):
        return Classification("Ideas", type_folder, 0.92, "File name or content suggests an idea or brainstorm.")
    if any(keyword in text for keyword in FINANCE_KEYWORDS):
        return Classification("Finance", type_folder, 0.9, "File name or content suggests finance or money records.")
    if any(keyword in text for keyword in MEETING_KEYWORDS):
        return Classification("Meetings", type_folder, 0.88, "File name or content suggests meeting notes or action items.")
    if any(keyword in text for keyword in BACKUP_KEYWORDS):
        return Classification("Backups", type_folder, 0.88, "File name suggests a backup or archived copy.")
    if any(keyword in text for keyword in COURSEWORK_KEYWORDS):
        return Classification("Coursework", type_folder, 0.88, "File name or content suggests class/course material.")
    if any(keyword in text for keyword in PERSONAL_KEYWORDS):
        return Classification("Personal", type_folder, 0.86, "File name or content suggests personal material.")
    return None


def _type_folder_for_purpose(signal: FileSignal) -> str | None:
    extension = signal.extension
    if extension in AUDIO_EXTENSIONS:
        return "Audio"
    if extension in VIDEO_EXTENSIONS:
        return "Videos"
    if extension in IMAGE_EXTENSIONS:
        return _image_subfolder(signal.name.lower())
    if extension in DOCUMENT_EXTENSIONS:
        return DOCUMENT_EXTENSIONS[extension][1]
    if extension in DATA_EXTENSIONS:
        return DATA_EXTENSIONS[extension][1]
    if extension in CODE_EXTENSIONS:
        return _code_subfolder(extension) or "Code"
    if extension in ARCHIVE_EXTENSIONS:
        return "Archives"
    return None


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
