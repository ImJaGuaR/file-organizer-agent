from __future__ import annotations

from pathlib import Path

from .models import Classification, FileSignal, MoveAction


def build_move_plan(
    signals: list[FileSignal],
    classifications: dict[Path, Classification],
    output_folder: Path,
) -> list[MoveAction]:
    output_folder = output_folder.expanduser().resolve()
    reserved_destinations: set[Path] = set()
    actions: list[MoveAction] = []

    for signal in signals:
        classification = classifications[signal.path]
        if not signal.path.exists():
            actions.append(
                MoveAction(
                    source=signal.path,
                    destination=signal.path,
                    classification=classification,
                    action="skip",
                    reason="Source file no longer exists.",
                )
            )
            continue

        destination_dir = output_folder.joinpath(*classification.folder_parts)
        destination = _unique_destination(destination_dir / signal.name, reserved_destinations)
        reserved_destinations.add(destination)
        if signal.path.resolve() == destination.resolve():
            actions.append(
                MoveAction(
                    source=signal.path,
                    destination=destination,
                    classification=classification,
                    action="skip",
                    reason="File is already in the correct destination.",
                )
            )
        else:
            actions.append(
                MoveAction(
                    source=signal.path,
                    destination=destination,
                    classification=classification,
                    action="move",
                    reason=classification.reason,
                )
            )
    return actions


def _unique_destination(destination: Path, reserved_destinations: set[Path]) -> Path:
    if destination not in reserved_destinations and not destination.exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if candidate not in reserved_destinations and not candidate.exists():
            return candidate
        counter += 1
