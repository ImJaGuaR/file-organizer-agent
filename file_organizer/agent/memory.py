from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from .schemas import MemoryItem, MemorySource


class NaturalLanguageMemory:
    def __init__(self, path: Path):
        self.path = path.expanduser()
        self.items: list[MemoryItem] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        raw_items = data.get("items", []) if isinstance(data, dict) else []
        self.items = [MemoryItem.from_dict(item) for item in raw_items if isinstance(item, dict)]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"items": [item.to_dict() for item in self.items]}, indent=2),
            encoding="utf-8",
        )

    def active_text(self) -> str:
        active = [item for item in self.items if item.active]
        if not active:
            return "(No saved preferences yet.)"
        return "\n".join(f"- {item.text}" for item in active)

    def add(self, text: str, source: MemorySource) -> MemoryItem:
        item = MemoryItem(
            id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            text=text.strip(),
            source=source,
            active=True,
        )
        self.items.append(item)
        self.save()
        return item

    def forget_all(self) -> None:
        self.items = [MemoryItem(item.id, item.created_at, item.text, item.source, False) for item in self.items]
        self.save()

    def list_items(self) -> list[MemoryItem]:
        return list(self.items)


def default_memory_path() -> Path:
    return Path.home() / ".file_organizer_agent" / "memory.json"

