from pathlib import Path

from file_organizer.models import Classification, FileSignal
from file_organizer.planner import build_move_plan


def make_signal(path: Path) -> FileSignal:
    return FileSignal(
        path=path,
        relative_path=Path(path.name),
        name=path.name,
        extension=path.suffix.lower(),
        size_bytes=1,
        modified_at="2026-01-01T00:00:00",
        created_at="2026-01-01T00:00:00",
        mime_type=None,
    )


def test_duplicate_destinations_are_renamed(tmp_path: Path) -> None:
    source_a = tmp_path / "a" / "report.pdf"
    source_b = tmp_path / "b" / "report.pdf"
    source_a.parent.mkdir()
    source_b.parent.mkdir()
    source_a.write_text("a")
    source_b.write_text("b")
    signals = [make_signal(source_a), make_signal(source_b)]
    classification = Classification("Documents", "PDFs", 0.9, "test")
    plan = build_move_plan(
        signals,
        {source_a: classification, source_b: classification},
        tmp_path / "Organized",
    )
    assert plan[0].destination.name == "report.pdf"
    assert plan[1].destination.name == "report (1).pdf"
