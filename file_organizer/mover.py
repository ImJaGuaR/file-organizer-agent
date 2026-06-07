from __future__ import annotations

from pathlib import Path
from shutil import move

from .models import MoveAction


def execute_plan(actions: list[MoveAction], apply: bool = False) -> list[str]:
    errors: list[str] = []
    if not apply:
        return errors

    for action in actions:
        if action.action != "move":
            continue
        try:
            action.destination.parent.mkdir(parents=True, exist_ok=True)
            move(str(action.source), str(action.destination))
        except OSError as exc:
            errors.append(f"{action.source} -> {action.destination}: {exc}")
    return errors


def ensure_output_folders(output_folder: Path) -> None:
    for parts in [
        ("Documents", "PDFs"),
        ("Documents", "Word"),
        ("Documents", "Text"),
        ("Documents", "Presentations"),
        ("Images", "Screenshots"),
        ("Images", "Photos"),
        ("Images", "Diagrams"),
        ("Images", "Other"),
        ("Code",),
        ("Data", "Spreadsheets"),
        ("Data", "CSV"),
        ("Data", "JSON"),
        ("Archives",),
        ("Audio",),
        ("Videos",),
        ("Research",),
        ("Review",),
        ("Reports",),
    ]:
        output_folder.joinpath(*parts).mkdir(parents=True, exist_ok=True)
