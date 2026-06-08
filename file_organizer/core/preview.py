from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from .safety import looks_secret


TEXT_LIKE_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
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
    ".log",
}


def read_file_preview(path: Path, max_chars: int = 1200, max_size_bytes: int = 512_000) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if looks_secret(path):
        return "", ["Preview skipped because filename looks sensitive."]
    if path.is_symlink():
        return "", ["Preview skipped for symlink."]
    try:
        if path.stat().st_size > max_size_bytes:
            return "", [f"Preview skipped because file is larger than {max_size_bytes} bytes."]
    except OSError as exc:
        return "", [f"Could not stat file for preview: {exc}"]

    extension = path.suffix.lower()
    try:
        if extension == ".docx":
            return inspect_docx_preview(path, max_chars), warnings
        if extension in TEXT_LIKE_EXTENSIONS:
            return _read_text_preview(path, max_chars), warnings
    except UnicodeDecodeError:
        warnings.append("Could not decode text preview.")
    except OSError as exc:
        warnings.append(f"Could not read preview: {exc}")
    except BadZipFile:
        warnings.append("DOCX preview failed because the file is not a valid zip archive.")
    except ET.ParseError:
        warnings.append("DOCX preview failed because document XML could not be parsed.")
    return "", warnings


def inspect_docx_preview(path: Path, max_chars: int = 1200) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
        if sum(len(item) for item in paragraphs) >= max_chars:
            break
    return "\n".join(paragraphs)[:max_chars].strip()


def _read_text_preview(path: Path, max_chars: int) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(max_chars).strip()

