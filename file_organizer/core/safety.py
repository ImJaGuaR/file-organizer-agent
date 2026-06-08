from __future__ import annotations

from pathlib import Path

from .paths import has_hidden_part


RISKY_FOLDER_NAMES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "Applications",
    "Library",
    "System",
    "Windows",
    "Program Files",
    "Program Files (x86)",
}

SECRET_NAME_FRAGMENTS = {
    ".env",
    "id_rsa",
    "id_dsa",
    "credentials",
    "credential",
    "password",
    "passwd",
    "token",
    "secret",
    "private_key",
    "apikey",
    "api_key",
}


def is_risky_root(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    home = Path.home().resolve()
    risky = {Path("/").resolve(), home}
    return resolved in risky or resolved.name in RISKY_FOLDER_NAMES


def risk_flags_for_path(path: Path, source_root: Path | None = None) -> list[str]:
    flags: list[str] = []
    name = path.name.lower()
    if has_hidden_part(path if source_root is None else path.relative_to(source_root)):
        flags.append("hidden")
    if path.is_symlink():
        flags.append("symlink")
    if path.name in RISKY_FOLDER_NAMES or any(part in RISKY_FOLDER_NAMES for part in path.parts):
        flags.append("protected_folder")
    if looks_secret(path):
        flags.append("secret_like_name")
    return flags


def looks_secret(path: Path) -> bool:
    name = path.name.lower()
    return any(fragment in name for fragment in SECRET_NAME_FRAGMENTS)


def safe_type_guess(path: Path, is_directory: bool) -> str:
    if is_directory:
        return "directory"
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"

