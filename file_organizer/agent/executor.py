from __future__ import annotations

from pathlib import Path
from shutil import move

from .schemas import ValidatedPlan


def apply_plan(plan: ValidatedPlan, apply: bool = False, confirmed_high_risk_ids: set[int] | None = None) -> dict[str, object]:
    result: dict[str, object] = {"applied": 0, "skipped": 0, "errors": [], "warnings": []}
    if not apply:
        return result
    confirmed_high_risk_ids = confirmed_high_risk_ids or set()
    errors: list[str] = []
    warnings: list[str] = []
    applied = 0
    skipped = 0

    for action in plan.actions:
        if action.action == "skip":
            skipped += 1
            continue
        if action.risk_level == "high" and action.id not in confirmed_high_risk_ids:
            warnings.append(f"Skipped high-risk action {action.id}; explicit high-risk confirmation was not provided.")
            skipped += 1
            continue
        if action.action == "delete":
            destination = plan.destination_root / "_To_Delete_Review" / action.source_path.name
            destination = _dedupe(destination)
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                move(str(action.source_path), str(destination))
                applied += 1
            except OSError as exc:
                errors.append(f"{action.source_path}: {exc}")
            continue
        if action.action == "move" and action.destination_path:
            try:
                action.destination_path.parent.mkdir(parents=True, exist_ok=True)
                move(str(action.source_path), str(action.destination_path))
                applied += 1
            except OSError as exc:
                errors.append(f"{action.source_path} -> {action.destination_path}: {exc}")

    result["applied"] = applied
    result["skipped"] = skipped
    result["errors"] = errors
    result["warnings"] = warnings
    return result


def _dedupe(destination: Path) -> Path:
    if not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination.parent / f"{destination.stem} ({counter}){destination.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

