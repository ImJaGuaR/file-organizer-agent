from __future__ import annotations

from datetime import datetime
from mimetypes import guess_type
from pathlib import Path

from .content_reader import read_preview
from .models import FileSignal


def scan_folder(
    target_folder: Path,
    output_folder: Path,
    recursive: bool = False,
    include_hidden: bool = False,
) -> list[FileSignal]:
    target_folder = target_folder.expanduser().resolve()
    output_folder = output_folder.expanduser().resolve()
    exclude_output_folder = _is_inside(output_folder, target_folder)
    pattern = "**/*" if recursive else "*"
    signals: list[FileSignal] = []

    for path in sorted(target_folder.glob(pattern)):
        if not path.is_file():
            continue
        if exclude_output_folder and _is_inside(path.resolve(), output_folder):
            continue
        if not include_hidden and _has_hidden_part(path.relative_to(target_folder)):
            continue

        stat = path.stat()
        preview, warnings = read_preview(path)
        mime_type, _ = guess_type(path.name)
        signals.append(
            FileSignal(
                path=path,
                relative_path=path.relative_to(target_folder),
                name=path.name,
                extension=path.suffix.lower(),
                size_bytes=stat.st_size,
                modified_at=_format_timestamp(stat.st_mtime),
                created_at=_format_timestamp(stat.st_ctime),
                mime_type=mime_type,
                preview=preview,
                warnings=warnings,
            )
        )
    return signals


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _is_inside(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _has_hidden_part(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)
