from __future__ import annotations

from pathlib import Path

DEFAULT_OUTPUT_FOLDER = "Organized"
REPORTS_FOLDER = "Reports"
DEFAULT_MODEL = "gpt-5.4-mini"

DOCUMENT_EXTENSIONS = {
    ".pdf": ("Documents", "PDFs"),
    ".doc": ("Documents", "Word"),
    ".docx": ("Documents", "Word"),
    ".txt": ("Documents", "Text"),
    ".rtf": ("Documents", "Text"),
    ".md": ("Documents", "Text"),
    ".ppt": ("Documents", "Presentations"),
    ".pptx": ("Documents", "Presentations"),
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".heic",
    ".svg",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".sh",
    ".html",
    ".css",
    ".sql",
    ".ipynb",
}

DATA_EXTENSIONS = {
    ".csv": ("Data", "CSV"),
    ".tsv": ("Data", "CSV"),
    ".json": ("Data", "JSON"),
    ".xml": ("Data", "XML"),
    ".yaml": ("Data", "YAML"),
    ".yml": ("Data", "YAML"),
    ".xlsx": ("Data", "Spreadsheets"),
    ".xls": ("Data", "Spreadsheets"),
    ".ods": ("Data", "Spreadsheets"),
}

RESEARCH_KEYWORDS = {
    "research",
    "paper",
    "journal",
    "citation",
    "references",
    "bibliography",
    "abstract",
    "methodology",
    "literature",
    "thesis",
    "assignment",
    "project",
    "milestone",
}

SCREENSHOT_KEYWORDS = {"screenshot", "screen shot", "capture"}
DIAGRAM_KEYWORDS = {"diagram", "flowchart", "architecture", "system", "uml"}


def default_memory_path() -> Path:
    return Path.home() / ".file_organizer_agent_memory.json"
