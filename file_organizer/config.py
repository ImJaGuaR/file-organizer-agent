from __future__ import annotations

from pathlib import Path


DEFAULT_OUTPUT_FOLDER = "Organized"
REPORTS_FOLDER = "Reports"
DEFAULT_MODEL = "gpt-5.4-mini"


def default_memory_path() -> Path:
    return Path.home() / ".file_organizer_agent" / "memory.json"

