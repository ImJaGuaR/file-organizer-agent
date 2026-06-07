from pathlib import Path

from file_organizer.interactive import _followup_requests, _resolve_output, _resolve_target, _resolve_task


def test_absolute_demo_path_stays_path() -> None:
    assert _resolve_target("/tmp/demo") == Path("/tmp/demo")


def test_folder_path_phrase_extracts_path_before_options() -> None:
    assert _resolve_target("folder /tmp/demo with AI") == Path("/tmp/demo")


def test_sample_phrase_uses_sample_folder() -> None:
    assert _resolve_target("organize the sample folder with AI labels") == Path("sample_messy_folder")


def test_user_folder_phrase_sets_home_output() -> None:
    assert _resolve_output("move all download folder content to the user folder") == Path.home()


def test_home_folder_phrase_sets_home_output() -> None:
    assert _resolve_output("organize Downloads under my home folder") == Path.home()


def test_explicit_output_path_is_used() -> None:
    assert _resolve_output("organize downloads output /tmp/sorted") == Path("/tmp/sorted")


def test_download_output_phrase_sets_downloads_output() -> None:
    assert _resolve_output("move all into download") == Path.home() / "Downloads"
    assert _resolve_output("move all to Downloads") == Path.home() / "Downloads"


def test_delete_words_set_delete_task() -> None:
    assert _resolve_task("delete trash in the trash can") == "delete"
    assert _resolve_task("empty trash can") == "delete"


def test_organize_words_default_to_organize_task() -> None:
    assert _resolve_task("organize my Downloads") == "organize"


def test_combined_organize_and_delete_starts_with_organize_then_queues_delete() -> None:
    request = "organize my Downloads and also delete trash in trash can"
    task = _resolve_task(request)
    assert task == "organize"
    assert _followup_requests(request, task) == ["delete trash in trash can"]
