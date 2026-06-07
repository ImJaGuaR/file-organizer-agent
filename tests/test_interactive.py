from pathlib import Path

from file_organizer.interactive import _resolve_target


def test_absolute_demo_path_stays_path() -> None:
    assert _resolve_target("/tmp/demo") == Path("/tmp/demo")


def test_folder_path_phrase_extracts_path_before_options() -> None:
    assert _resolve_target("folder /tmp/demo with AI") == Path("/tmp/demo")


def test_sample_phrase_uses_sample_folder() -> None:
    assert _resolve_target("organize the sample folder with AI labels") == Path("sample_messy_folder")
