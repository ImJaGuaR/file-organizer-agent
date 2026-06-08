from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from file_organizer.agent.planner import AgentPlanningError, propose_plan, validate_plan
from file_organizer.agent.schemas import FileMetadata, OrganizationPlan, PlanValidationError
from file_organizer.providers.base import ProviderConfig, ProviderUnavailable


class FakeProvider:
    config = ProviderConfig(provider="fake", model="fake-model")

    def __init__(self, responses: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.responses = responses or []
        self.error = error
        self.calls = 0

    def generate_structured(self, messages, schema, schema_name):
        self.calls += 1
        if self.error:
            raise self.error
        return self.responses.pop(0)

    def auth_status(self):
        return {}


def metadata(path: Path, root: Path) -> FileMetadata:
    return FileMetadata(
        path=str(path),
        relative_path=str(path.relative_to(root)),
        name=path.name,
        extension=path.suffix,
        size_bytes=path.stat().st_size,
        modified_at="2026-01-01T00:00:00",
        mime_type=None,
        safe_type_guess=path.suffix.lstrip(".") or "unknown",
        is_hidden=False,
        is_directory=False,
        is_symlink=False,
        preview="operating systems assignment notes",
    )


def plan_dict(source: Path, destination: str = "University/Operating Systems/notes.txt") -> dict[str, Any]:
    return {
        "request_summary": "Organize course files.",
        "source_root": str(source.parent),
        "destination_root": str(source.parent / "Organized"),
        "mode": "preview",
        "requires_approval": True,
        "global_reasoning": "Grouped by course based on preview.",
        "actions": [
            {
                "id": 1,
                "action": "move",
                "source_path": str(source),
                "destination_path": destination,
                "confidence": 0.9,
                "reasoning": "The preview mentions operating systems coursework.",
                "evidence": ["preview: operating systems assignment notes"],
                "risk_level": "low",
                "needs_user_confirmation": False,
            }
        ],
        "questions": [],
        "warnings": [],
    }


def test_ai_unavailable_has_no_rule_fallback(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    provider = FakeProvider(error=ProviderUnavailable("missing key"))

    with pytest.raises(AgentPlanningError, match="missing key"):
        propose_plan(provider, "organize", [metadata(source, tmp_path)], "", tmp_path, tmp_path / "Organized", {})


def test_invalid_ai_json_repairs_once(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    invalid = {"request_summary": "broken"}
    provider = FakeProvider([invalid, plan_dict(source)])

    plan = propose_plan(provider, "organize", [metadata(source, tmp_path)], "", tmp_path, tmp_path / "Organized", {})

    assert provider.calls == 2
    assert plan.actions[0].destination_path == "University/Operating Systems/notes.txt"


def test_invalid_ai_json_fails_after_one_repair(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    provider = FakeProvider([{"request_summary": "broken"}, {"request_summary": "still broken"}])

    with pytest.raises(AgentPlanningError, match="repair failed"):
        propose_plan(provider, "organize", [metadata(source, tmp_path)], "", tmp_path, tmp_path / "Organized", {})


def test_validation_blocks_path_traversal(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    plan = OrganizationPlan.from_dict(plan_dict(source, "../escape.txt"))

    with pytest.raises(PlanValidationError, match="path traversal"):
        validate_plan(plan, tmp_path, tmp_path / "Organized")


def test_validation_blocks_destination_outside_root(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    plan = OrganizationPlan.from_dict(plan_dict(source, str(tmp_path.parent / "escape.txt")))

    with pytest.raises(PlanValidationError, match="escapes allowed root"):
        validate_plan(plan, tmp_path, tmp_path / "Organized")


def test_duplicate_destinations_renamed_safely(tmp_path: Path) -> None:
    source_a = tmp_path / "a.txt"
    source_b = tmp_path / "b.txt"
    source_a.write_text("a")
    source_b.write_text("b")
    data = plan_dict(source_a, "University/OS/report.txt")
    data["actions"].append({**data["actions"][0], "id": 2, "source_path": str(source_b)})
    plan = OrganizationPlan.from_dict(data)

    validated = validate_plan(plan, tmp_path, tmp_path / "Organized")

    assert validated.actions[0].destination_path.name == "report.txt"
    assert validated.actions[1].destination_path.name == "report (1).txt"

