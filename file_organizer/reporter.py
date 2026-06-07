from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from .console import heading, label, muted, rule, shorten_path, status
from .config import REPORTS_FOLDER
from .models import MoveAction, OrganizationReport


def print_plan(actions: list[MoveAction], dry_run: bool, interactive_apply_prompt: bool = False) -> None:
    mode = "Preview plan" if dry_run else "Applying plan"
    tone = "yellow" if dry_run else "green"
    move_count = sum(1 for action in actions if action.action == "move")
    delete_count = sum(1 for action in actions if action.action == "delete")
    skip_count = sum(1 for action in actions if action.action == "skip")

    print()
    print(heading("Organization Plan"))
    print(rule())
    print(f"{label('Mode')}       {status(mode, tone)}")
    print(f"{label('Files')}      {len(actions)} scanned, {move_count} move, {delete_count} delete, {skip_count} skip")
    print(rule())

    for index, action in enumerate(actions, start=1):
        classification = action.classification
        category = _category_label(classification.category, classification.subfolder)
        source_label = _source_label(classification.source)
        tone = "green" if action.action == "move" else "yellow"

        print(f"{status(f'{index:02d}. {action.action.upper()}', tone)}  {category}")
        if action.action == "delete":
            print(f"    {muted('file')} {shorten_path(action.source)}")
        else:
            print(f"    {muted('from')} {shorten_path(action.source)}")
            print(f"    {muted('to  ')} {shorten_path(action.destination)}")
        if action.classification.summary:
            print(f"    {label('summary')} {action.classification.summary}")
        print(f"    {label('why')}     {action.reason}")
        print(f"    {label('signal')}  confidence {classification.confidence:.2f} | {source_label}")
        print()
    print(rule())
    if dry_run:
        if interactive_apply_prompt:
            print(
                status("No files were changed yet.", "yellow")
                + " Type APPLY to apply, or FIX 2 Folder/Subfolder to correct and teach the agent."
            )
        else:
            print(status("No files were changed.", "yellow") + " Run again with --apply to apply the plan.")
    else:
        print(status("Done.", "green") + " Files were changed according to the plan.")


def print_apply_result(errors: list[str]) -> None:
    print()
    print(rule())
    if errors:
        print(status("Apply finished with errors.", "yellow"))
        for error in errors:
            print(f"- {error}")
    else:
        print(status("Done.", "green") + " Files were changed according to the approved plan.")


def _category_label(category: str, subfolder: str | None) -> str:
    path = f"{category}/{subfolder}" if subfolder else category
    return label(path)


def _source_label(source: str) -> str:
    labels = {
        "rules": "local rules",
        "memory": "learned memory",
        "user-request": "user request",
        "ai-openai-compatible": "AI label",
        "ai-openai": "AI label",
        "ai-ollama": "AI label",
        "ai-fallback": "AI tried, rules kept it safe",
        "ai-error": "AI error, rules kept it safe",
        "ai-unavailable": "AI unavailable, rules kept it safe",
    }
    return labels.get(source, source)


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
        f"- Deletes planned/executed: `{counts.get('delete', 0)}`",
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
