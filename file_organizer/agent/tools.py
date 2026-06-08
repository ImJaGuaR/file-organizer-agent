from __future__ import annotations

from pathlib import Path

from file_organizer.core.preview import inspect_docx_preview, read_file_preview
from file_organizer.core.reports import write_report
from file_organizer.core.scanner import scan_directory

from .executor import apply_plan
from .memory import NaturalLanguageMemory
from .planner import validate_plan
from .schemas import OrganizationPlan, ValidatedPlan


def scan_directory_tool(path: str, recursive: bool, max_files: int):
    return scan_directory(Path(path), recursive=recursive, max_files=max_files)


def read_file_preview_tool(path: str, max_chars: int):
    return read_file_preview(Path(path), max_chars=max_chars)


def inspect_docx_preview_tool(path: str):
    return inspect_docx_preview(Path(path))


def validate_plan_tool(plan: OrganizationPlan, source_root: Path, destination_root: Path) -> ValidatedPlan:
    return validate_plan(plan, source_root, destination_root)


def apply_plan_tool(plan: ValidatedPlan, approved: bool):
    return apply_plan(plan, apply=approved)


def write_report_tool(*args, **kwargs):
    return write_report(*args, **kwargs)


def save_memory_tool(memory: NaturalLanguageMemory, note: str):
    return memory.add(note, "user_correction")


def read_memory_tool(memory: NaturalLanguageMemory) -> str:
    return memory.active_text()

