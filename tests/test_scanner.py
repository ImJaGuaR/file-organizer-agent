from pathlib import Path

from file_organizer.scanner import scan_folder


def test_scans_target_when_output_is_parent_folder(tmp_path: Path) -> None:
    target = tmp_path / "Downloads"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")

    signals = scan_folder(target, tmp_path)

    assert [signal.name for signal in signals] == ["notes.txt"]


def test_skips_output_folder_when_output_is_inside_target(tmp_path: Path) -> None:
    target = tmp_path / "Downloads"
    output = target / "Organized"
    output.mkdir(parents=True)
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    already_organized = output / "old.txt"
    already_organized.write_text("old notes", encoding="utf-8")

    signals = scan_folder(target, output, recursive=True)

    assert [signal.name for signal in signals] == ["notes.txt"]
