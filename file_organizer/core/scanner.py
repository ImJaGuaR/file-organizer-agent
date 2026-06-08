from __future__ import annotations

from datetime import datetime
from mimetypes import guess_type
from pathlib import Path

from file_organizer.agent.schemas import FileMetadata

from .paths import has_hidden_part, is_inside
from .preview import read_file_preview
from .safety import RISKY_FOLDER_NAMES, looks_secret, risk_flags_for_path, safe_type_guess


def scan_directory(
    path: Path,
    recursive: bool = False,
    max_files: int = 200,
    include_hidden: bool = False,
    include_risky: bool = False,
    output_root: Path | None = None,
    preview_chars: int = 1200,
) -> list[FileMetadata]:
    root = path.expanduser().resolve()
    pattern = "**/*" if recursive else "*"
    files: list[FileMetadata] = []
    output_root = output_root.expanduser().resolve() if output_root else None

    for candidate in sorted(root.glob(pattern)):
        if len(files) >= max_files:
            break
        if output_root and is_inside(candidate, output_root):
            continue
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        if not include_hidden and has_hidden_part(relative):
            continue
        if not include_risky and any(part in RISKY_FOLDER_NAMES for part in relative.parts):
            continue
        if candidate.is_symlink():
            if include_risky:
                files.append(_metadata(candidate, root, preview_chars=0))
            continue
        if candidate.is_dir():
            if include_risky and candidate.name in {".git", "node_modules", "venv", ".venv"}:
                files.append(_metadata(candidate, root, preview_chars=0))
            continue
        if not candidate.is_file():
            continue
        flags = risk_flags_for_path(candidate, root)
        if flags and not include_risky:
            warning = (
                "Preview skipped because filename looks sensitive."
                if looks_secret(candidate)
                else "Skipped risky preview."
            )
            files.append(_metadata(candidate, root, preview_chars=0, extra_warnings=[warning]))
            continue
        files.append(_metadata(candidate, root, preview_chars=preview_chars))
    return files


def _metadata(
    path: Path,
    root: Path,
    preview_chars: int,
    extra_warnings: list[str] | None = None,
) -> FileMetadata:
    stat = path.lstat()
    is_directory = path.is_dir()
    mime_type, _ = guess_type(path.name)
    preview = ""
    preview_warnings = list(extra_warnings or [])
    if preview_chars > 0 and path.is_file():
        preview, preview_warnings = read_file_preview(path, max_chars=preview_chars)
        preview_warnings.extend(extra_warnings or [])
    return FileMetadata(
        path=str(path.resolve()),
        relative_path=str(path.relative_to(root)),
        name=path.name,
        extension=path.suffix.lower(),
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        mime_type=mime_type,
        safe_type_guess=safe_type_guess(path, is_directory),
        is_hidden=has_hidden_part(path.relative_to(root)),
        is_directory=is_directory,
        is_symlink=path.is_symlink(),
        risk_flags=risk_flags_for_path(path, root),
        preview=preview,
        preview_warnings=preview_warnings,
    )
