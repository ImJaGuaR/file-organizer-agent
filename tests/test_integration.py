from pathlib import Path
import io
import sys

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


def test_apply_creates_only_needed_output_folders(tmp_path: Path) -> None:
    target = tmp_path / "messy"
    output = tmp_path / "organized-output"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    exit_code = main([str(target), "--output", str(output), "--apply", "--no-report"])

    assert exit_code == 0
    assert (output / "Documents" / "Text" / "notes.txt").exists()
    assert not (output / "Images").exists()
    assert not (output / "Research").exists()


class TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_interactive_preview_can_apply_same_plan(tmp_path: Path, capsys) -> None:
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\nAPPLY\n")
    try:
        exit_code = main(["--interactive", str(target), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Type APPLY" in output
    assert "Intelligence" not in output
    assert "Decision style" not in output
    assert not source.exists()
    assert (target / "Organized" / "Documents" / "Text" / "notes.txt").exists()


def test_interactive_preview_enter_leaves_files(tmp_path: Path, capsys) -> None:
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Type APPLY" in output
    assert "Okay, no files were moved." in output
    assert source.exists()


def test_interactive_keeps_explicit_target_when_prompt_mentions_downloads(tmp_path: Path, capsys) -> None:
    target = tmp_path / "Downloads"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("move all download folder content to the user folder\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Target          {target}" in output
    assert f"Output          {Path.home()}" in output
    assert "inside target folder: Organized" not in output
    assert source.exists()


def test_interactive_defaults_to_ai_first(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--env-file", str(tmp_path / "missing.env"), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "AI requested, but" in output
    assert "local rules" not in output
    assert source.exists()


def test_interactive_delete_preview_leaves_files(tmp_path: Path, capsys) -> None:
    target = tmp_path / "trash"
    target.mkdir()
    source = target / "old.txt"
    source.write_text("old", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("delete folder\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Task            Delete" in output
    assert "01. DELETE" in output
    assert "No files were changed yet." in output
    assert source.exists()


def test_interactive_delete_apply_removes_files_and_folders(tmp_path: Path, capsys) -> None:
    target = tmp_path / "trash"
    nested = target / "old-folder"
    nested.mkdir(parents=True)
    source = target / "old.txt"
    nested_file = nested / "nested.txt"
    source.write_text("old", encoding="utf-8")
    nested_file.write_text("nested", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("delete folder\nAPPLY\n")
    try:
        exit_code = main(["--interactive", str(target), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "01. DELETE" in output
    assert not source.exists()
    assert not nested.exists()


def test_interactive_fix_updates_plan_and_learns_filename(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    memory_file = tmp_path / "memory.json"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\nFIX 1 Coursework/Text\n\n")
    try:
        exit_code = main(
            [
                "--interactive",
                str(target),
                "--memory-file",
                str(memory_file),
                "--env-file",
                str(tmp_path / "missing.env"),
                "--no-report",
            ]
        )
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Coursework/Text" in output
    assert "User correction saved to memory." in output
    assert source.exists()

    exit_code = main([str(target), "--memory-file", str(memory_file), "--no-report"])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Coursework/Text" in output
    assert "learned memory" in output


def test_interactive_natural_language_output_correction_retargets_plan(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\nmove to user folder\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--env-file", str(tmp_path / "missing.env"), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Okay, I updated the output folder to {Path.home()}" in output
    assert "to   ~/Documents/Text/notes.txt" in output
    assert source.exists()


def test_interactive_download_output_correction_retargets_plan(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\nmove all into download\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--env-file", str(tmp_path / "missing.env"), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Okay, I updated the output folder to {Path.home() / 'Downloads'}" in output
    assert "to   ~/Downloads/Documents/Text/notes.txt" in output
    assert source.exists()


def test_interactive_fix_all_output_correction_retargets_plan(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    target.mkdir()
    source = target / "notes.txt"
    source.write_text("plain notes", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput("show the plan\nFIX all move to user folder\n\n")
    try:
        exit_code = main(["--interactive", str(target), "--env-file", str(tmp_path / "missing.env"), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"Okay, I updated the output folder to {Path.home()}" in output
    assert "to   ~/Documents/Text/notes.txt" in output
    assert source.exists()


def test_interactive_session_accepts_multiple_requests(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    messy = tmp_path / "messy"
    trash = tmp_path / "trash"
    messy.mkdir()
    trash.mkdir()
    messy_file = messy / "notes.txt"
    trash_file = trash / "old.txt"
    messy_file.write_text("plain notes", encoding="utf-8")
    trash_file.write_text("old", encoding="utf-8")
    old_stdin = sys.stdin
    sys.stdin = TtyInput(
        f"organize folder {messy}\n\n"
        f"delete folder {trash}\n\n"
        "\n"
    )
    try:
        exit_code = main(["--env-file", str(tmp_path / "missing.env"), "--no-report"])
    finally:
        sys.stdin = old_stdin

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Task            Organize" in output
    assert "Task            Delete" in output
    assert "01. MOVE" in output
    assert "01. DELETE" in output
    assert messy_file.exists()
    assert trash_file.exists()
