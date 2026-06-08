from __future__ import annotations

from pathlib import Path

from file_organizer.agent.executor import apply_plan
from file_organizer.agent.loop import AgentLoop
from file_organizer.agent.memory import NaturalLanguageMemory
from file_organizer.agent.schemas import OrganizationPlan
from file_organizer.agent.planner import validate_plan
from file_organizer.core.scanner import scan_directory
from file_organizer.providers.base import ProviderConfig


class FakeProvider:
    config = ProviderConfig(provider="fake", model="fake-model")

    def generate_structured(self, messages, schema, schema_name):
        raise AssertionError("FakeProvider should not be called in these tests")

    def auth_status(self):
        return {}


def plan_dict(source: Path, destination: str = "University/Operating Systems/notes.txt"):
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


def test_preview_mode_never_moves_files(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    plan = validate_plan(OrganizationPlan.from_dict(plan_dict(source)), tmp_path, tmp_path / "Organized")

    result = apply_plan(plan, apply=False)

    assert result["applied"] == 0
    assert source.exists()


def test_apply_moves_files(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    plan = validate_plan(OrganizationPlan.from_dict(plan_dict(source)), tmp_path, tmp_path / "Organized")

    result = apply_plan(plan, apply=True)

    assert result["applied"] == 1
    assert not source.exists()
    assert (tmp_path / "Organized" / "University" / "Operating Systems" / "notes.txt").exists()


def test_hidden_and_system_risky_files_skipped_by_default(tmp_path: Path) -> None:
    hidden = tmp_path / ".hidden.txt"
    visible = tmp_path / "visible.txt"
    hidden.write_text("hidden")
    visible.write_text("visible")
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "dep.txt").write_text("dep")

    files = scan_directory(tmp_path, recursive=True)

    assert [file.name for file in files] == ["visible.txt"]


def test_secret_like_files_are_not_previewed(tmp_path: Path) -> None:
    secret = tmp_path / "api_token.txt"
    secret.write_text("super secret token")

    files = scan_directory(tmp_path)

    assert files[0].preview == ""
    assert "sensitive" in files[0].preview_warnings[0]


def test_user_edit_updates_plan_and_saves_natural_language_memory(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    memory_file = tmp_path / "memory.json"
    memory = NaturalLanguageMemory(memory_file)
    loop = AgentLoop(FakeProvider(), memory)
    validated = validate_plan(OrganizationPlan.from_dict(plan_dict(source)), tmp_path, tmp_path / "Organized")

    edited = loop._edit(validated, "1 University/OS")

    assert edited.actions[0].destination_path == tmp_path / "Organized" / "University" / "OS" / "notes.txt"
    assert "User prefers University/OS" in memory.active_text()


def test_user_skip_changes_action_to_skip(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("notes")
    memory = NaturalLanguageMemory(tmp_path / "memory.json")
    loop = AgentLoop(FakeProvider(), memory)
    validated = validate_plan(OrganizationPlan.from_dict(plan_dict(source)), tmp_path, tmp_path / "Organized")

    skipped = loop._change_action(validated, "1", "skip")

    assert skipped.actions[0].action == "skip"
    assert skipped.actions[0].destination_path is None


def test_default_source_contains_no_hardcoded_extension_classification() -> None:
    root = Path(__file__).resolve().parents[1] / "file_organizer"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))

    forbidden = [
        "DOCUMENT_EXTENSIONS",
        "IMAGE_EXTENSIONS",
        "CODE_EXTENSIONS",
        "classify_with_rules",
        "Matched document extension",
        "used rule classification",
        "learn_extension",
    ]
    for token in forbidden:
        assert token not in source
