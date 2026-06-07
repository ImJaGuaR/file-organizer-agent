from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class OrganizerMemory:
    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.data: dict[str, Any] = {"extensions": {}, "name_contains": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(loaded, dict):
            self.data.update(loaded)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def learn_extension(self, extension: str, folder: str) -> None:
        normalized = extension.lower()
        if not normalized.startswith("."):
            normalized = f".{normalized}"
        self.data.setdefault("extensions", {})[normalized] = folder
        self.save()

    def classify_extension(self, extension: str) -> tuple[str, str | None] | None:
        folder = self.data.get("extensions", {}).get(extension.lower())
        return _split_folder(folder) if folder else None

    def classify_name(self, name: str) -> tuple[str, str | None] | None:
        lowered = name.lower()
        for pattern, folder in self.data.get("name_contains", {}).items():
            if pattern.lower() in lowered:
                return _split_folder(folder)
        return None


def _split_folder(folder: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in folder.replace("\\", "/").split("/") if part.strip()]
    if not parts:
        return "Review", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], "/".join(parts[1:])
