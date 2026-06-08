from __future__ import annotations

from pathlib import Path

from file_organizer.cli import main


def test_cli_without_provider_key_fails_clearly(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    target = tmp_path / "messy"
    target.mkdir()
    (target / "notes.txt").write_text("notes")

    exit_code = main([str(target), "--env-file", str(tmp_path / "missing.env"), "--no-report"])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert "AI provider unavailable, cannot create semantic organization plan" in output
    assert (target / "notes.txt").exists()

