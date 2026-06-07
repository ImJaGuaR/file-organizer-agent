from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileSignal:
    path: Path
    relative_path: Path
    name: str
    extension: str
    size_bytes: int
    modified_at: str
    created_at: str
    mime_type: str | None
    preview: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Classification:
    category: str
    subfolder: str | None
    confidence: float
    reason: str
    source: str = "rules"
    summary: str | None = None

    @property
    def folder_parts(self) -> tuple[str, ...]:
        if self.subfolder:
            return (self.category, self.subfolder)
        return (self.category,)


@dataclass(frozen=True)
class MoveAction:
    source: Path
    destination: Path
    classification: Classification
    action: str
    reason: str


@dataclass
class OrganizationReport:
    target_folder: Path
    output_folder: Path
    dry_run: bool
    actions: list[MoveAction]
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
