from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from file_organizer.agent.schemas import OrganizationPlan, ValidatedPlan


def write_report(
    plan: ValidatedPlan,
    result: dict[str, Any],
    request: str,
    provider: str,
    model: str | None,
    files_scanned: int,
    files_previewed: int,
    user_edits: list[str] | None = None,
    memory_updates: list[str] | None = None,
) -> tuple[Path, Path]:
    reports_dir = plan.destination_root / "Reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = reports_dir / f"agent-organization-report-{timestamp}.json"
    md_path = reports_dir / f"agent-organization-report-{timestamp}.md"
    payload = {
        "timestamp": timestamp,
        "request": request,
        "source_folder": str(plan.source_root),
        "destination_folder": str(plan.destination_root),
        "provider": provider,
        "model": model,
        "files_scanned": files_scanned,
        "files_previewed": files_previewed,
        "actions_proposed": len(plan.actions),
        "actions_applied": result.get("applied", 0),
        "skipped_items": result.get("skipped", 0),
        "warnings": plan.warnings + result.get("warnings", []),
        "user_edits": user_edits or [],
        "memory_updates": memory_updates or [],
        "errors": result.get("errors", []),
        "plan": plan.to_plan().to_dict(),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload, plan.to_plan()), encoding="utf-8")
    return json_path, md_path


def _markdown(payload: dict[str, Any], plan: OrganizationPlan) -> str:
    counts = Counter(action.action for action in plan.actions)
    lines = [
        "# AI File Organizer Report",
        "",
        f"- Request: {payload['request']}",
        f"- Source folder: `{payload['source_folder']}`",
        f"- Destination folder: `{payload['destination_folder']}`",
        f"- Provider/model: `{payload['provider']}` / `{payload['model']}`",
        f"- Files scanned: `{payload['files_scanned']}`",
        f"- Files previewed: `{payload['files_previewed']}`",
        f"- Proposed moves: `{counts.get('move', 0)}`",
        f"- Proposed deletes: `{counts.get('delete', 0)}`",
        f"- Skipped: `{counts.get('skip', 0)}`",
        "",
        "## Reasoning",
        "",
        plan.global_reasoning,
        "",
        "## Actions",
        "",
    ]
    for action in plan.actions:
        destination = action.destination_path or "(none)"
        lines.append(f"- **{action.action.upper()}** `{action.source_path}` -> `{destination}`")
        lines.append(f"  - Reason: {action.reasoning}")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    if payload["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    lines.append("")
    return "\n".join(lines)

