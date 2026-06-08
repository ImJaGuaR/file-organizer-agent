from __future__ import annotations

import re
from pathlib import Path


def is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def has_hidden_part(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def sanitize_path_part(value: str) -> str:
    value = value.replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9 ._()/\\-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" ._-/")
    if value in {"", ".", ".."}:
        return "Review"
    return value[:80]


def sanitize_relative_path(value: str) -> Path:
    raw_parts = [part for part in value.replace("\\", "/").split("/") if part.strip()]
    safe_parts: list[str] = []
    for part in raw_parts:
        if part in {".", ".."}:
            continue
        safe = sanitize_path_part(part)
        if safe:
            safe_parts.append(safe)
    if not safe_parts:
        raise ValueError("Destination path is empty after sanitization.")
    return Path(*safe_parts)


def unique_destination(destination: Path, reserved_destinations: set[Path] | None = None) -> Path:
    reserved_destinations = reserved_destinations or set()
    if destination not in reserved_destinations and not destination.exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if candidate not in reserved_destinations and not candidate.exists():
            return candidate
        counter += 1


def display_path(path: Path) -> str:
    home = Path.home()
    try:
        return "~/" + str(path.resolve().relative_to(home))
    except ValueError:
        return str(path)
