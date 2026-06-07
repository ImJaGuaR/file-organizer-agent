from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from .config import REPORTS_FOLDER
from .models import MoveAction, OrganizationReport


def print_plan(actions: list[MoveAction], dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "APPLY"
    print(f"\nFile Organizer Agent - {mode}")
    print("=" * 72)
    for action in actions:
        rel_source = action.source
        rel_destination = action.destination
        print(f"[{action.action.upper()}] {rel_source} -> {rel_destination}")
        print(
            f"  category={action.classification.category}"
            f"/{action.classification.subfolder or ''}"
            f" confidence={action.classification.confidence:.2f}"
            f" source={action.classification.source}"
        )
        if action.classification.summary:
            print(f"  summary={action.classification.summary}")
        print(f"  reason={action.reason}")
    print("=" * 72)
    if dry_run:
        print("No files were moved. Run again with --apply to execute this plan.")


def write_reports(report: OrganizationReport) -> tuple[Path, Path]:
    reports_dir = report.output_folder / REPORTS_FOLDER
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = reports_dir / f"organization-report-{timestamp}.json"
    md_path = reports_dir / f"organization-report-{timestamp}.md"

    json_path.write_text(
        json.dumps(_report_to_dict(report), indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    return json_path, md_path


def _report_to_dict(report: OrganizationReport) -> dict[str, object]:
    return {
        "target_folder": str(report.target_folder),
        "output_folder": str(report.output_folder),
        "dry_run": report.dry_run,
        "metadata": report.metadata,
        "errors": report.errors,
        "actions": [
            {
                "action": action.action,
                "source": str(action.source),
                "destination": str(action.destination),
                "category": action.classification.category,
                "subfolder": action.classification.subfolder,
                "confidence": action.classification.confidence,
                "classification_source": action.classification.source,
                "summary": action.classification.summary,
                "reason": action.reason,
            }
            for action in report.actions
        ],
    }


def _report_to_markdown(report: OrganizationReport) -> str:
    counts = Counter(action.action for action in report.actions)
    category_counts = Counter(action.classification.category for action in report.actions)
    lines = [
        "# File Organizer Report",
        "",
        f"- Target folder: `{report.target_folder}`",
        f"- Output folder: `{report.output_folder}`",
        f"- Dry run: `{report.dry_run}`",
        f"- Files scanned: `{len(report.actions)}`",
        f"- Moves planned/executed: `{counts.get('move', 0)}`",
        f"- Skipped: `{counts.get('skip', 0)}`",
        "",
        "## Categories",
        "",
    ]
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")
    if report.errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report.errors)
    lines.extend(["", "## Actions", ""])
    for action in report.actions:
        lines.append(
            f"- **{action.action.upper()}** `{action.source}` -> `{action.destination}` "
            f"({action.classification.category}/{action.classification.subfolder or ''}, "
            f"{action.classification.source}, {action.classification.confidence:.2f})"
        )
    lines.append("")
    return "\n".join(lines)
