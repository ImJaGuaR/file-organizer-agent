from pathlib import Path

from file_organizer.cli import main


def test_dry_run_does_not_move_files(tmp_path: Path) -> None:
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    exit_code = main([str(target), "--no-report"])
    assert exit_code == 0
    assert source.exists()
    assert not (target / "Organized" / "Documents" / "Text" / "notes.txt").exists()


def test_apply_moves_files(tmp_path: Path) -> None:
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    exit_code = main([str(target), "--apply", "--no-report"])
    assert exit_code == 0
    assert not source.exists()
    assert (target / "Organized" / "Documents" / "Text" / "notes.txt").exists()
