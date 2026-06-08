from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from file_organizer.core.paths import is_inside, sanitize_relative_path, unique_destination
from file_organizer.core.safety import RISKY_FOLDER_NAMES, is_risky_root, risk_flags_for_path
from file_organizer.providers.base import AIProvider, ProviderError

from .prompts import ORGANIZER_SYSTEM_PROMPT, PLAN_USER_PROMPT, REPAIR_PROMPT, REVISION_PROMPT
from .schemas import (
    PLAN_JSON_SCHEMA,
    FileMetadata,
    OrganizationPlan,
    PlanAction,
    PlanValidationError,
    ValidatedAction,
    ValidatedPlan,
)


class AgentPlanningError(RuntimeError):
    """Raised when the AI agent cannot produce a valid semantic plan."""


def propose_plan(
    provider: AIProvider,
    user_request: str,
    files: list[FileMetadata],
    memory: str,
    source_root: Path,
    destination_root: Path,
    constraints: dict[str, Any],
) -> OrganizationPlan:
    files_json = json.dumps([file.to_model_dict() for file in files], indent=2)
    messages = [
        {"role": "system", "content": ORGANIZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PLAN_USER_PROMPT.format(
                request=user_request,
                source_root=str(source_root),
                destination_root=str(destination_root),
                constraints=json.dumps(constraints, indent=2),
                memory=memory,
                files_json=files_json,
            ),
        },
    ]
    raw: dict[str, Any] | None = None
    try:
        raw = provider.generate_structured(messages, PLAN_JSON_SCHEMA, "organization_plan")
        return OrganizationPlan.from_dict(raw)
    except (PlanValidationError, ProviderError, ValueError, TypeError) as exc:
        if raw is None:
            raise AgentPlanningError(str(exc)) from exc
        return _repair_plan(provider, messages, raw, exc)


def revise_plan(
    provider: AIProvider,
    user_request: str,
    revision: str,
    current_plan: OrganizationPlan,
    memory: str,
) -> OrganizationPlan:
    messages = [
        {"role": "system", "content": ORGANIZER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": REVISION_PROMPT.format(
                request=user_request,
                revision=revision,
                plan_json=json.dumps(current_plan.to_dict(), indent=2),
                memory=memory,
            ),
        },
    ]
    raw: dict[str, Any] | None = None
    try:
        raw = provider.generate_structured(messages, PLAN_JSON_SCHEMA, "organization_plan")
        return OrganizationPlan.from_dict(raw)
    except (PlanValidationError, ProviderError, ValueError, TypeError) as exc:
        if raw is None:
            raise AgentPlanningError(str(exc)) from exc
        return _repair_plan(provider, messages, raw, exc)


def validate_plan(
    plan: OrganizationPlan,
    source_root: Path,
    destination_root: Path,
    allow_outside_destination: bool = False,
) -> ValidatedPlan:
    source_root = source_root.expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()
    if is_risky_root(source_root):
        raise PlanValidationError(f"Refusing to organize risky root: {source_root}")
    if not source_root.exists() or not source_root.is_dir():
        raise PlanValidationError(f"Source root does not exist: {source_root}")

    source_paths = _all_source_paths(source_root)
    reserved_destinations: set[Path] = set()
    validated_actions: list[ValidatedAction] = []
    seen_ids: set[int] = set()
    for action in plan.actions:
        if action.id in seen_ids:
            raise PlanValidationError(f"Duplicate action id: {action.id}")
        seen_ids.add(action.id)
        source_path = _resolve_source(action.source_path, source_root)
        if source_path not in source_paths:
            raise PlanValidationError(f"Action {action.id} source is missing or outside source root: {action.source_path}")
        if any(part in RISKY_FOLDER_NAMES for part in source_path.parts):
            raise PlanValidationError(f"Action {action.id} touches a protected folder: {source_path}")
        if source_path.is_symlink():
            raise PlanValidationError(f"Action {action.id} touches a symlink: {source_path}")

        destination_path = None
        if action.action == "move":
            if not action.destination_path:
                raise PlanValidationError(f"Move action {action.id} requires destination_path")
            destination_path = _resolve_destination(
                action.destination_path,
                destination_root,
                allow_outside_destination,
            )
            destination_path = unique_destination(destination_path, reserved_destinations)
            reserved_destinations.add(destination_path)
            if destination_path == source_path:
                action = PlanAction(
                    id=action.id,
                    action="skip",
                    source_path=action.source_path,
                    destination_path=None,
                    confidence=action.confidence,
                    reasoning="Source is already at the proposed destination.",
                    evidence=action.evidence,
                    risk_level=action.risk_level,
                    needs_user_confirmation=action.needs_user_confirmation,
                )
                destination_path = None
        elif action.action in {"skip", "delete"} and action.destination_path:
            destination_path = None

        flags = risk_flags_for_path(source_path, source_root)
        risk_level = action.risk_level
        needs_confirmation = action.needs_user_confirmation
        if action.action == "delete":
            risk_level = "high"
            needs_confirmation = True
        if flags:
            risk_level = "high" if "secret_like_name" in flags or "protected_folder" in flags else risk_level
            needs_confirmation = True

        validated_actions.append(
            ValidatedAction(
                id=action.id,
                action=action.action,
                source_path=source_path,
                destination_path=destination_path,
                confidence=action.confidence,
                reasoning=action.reasoning,
                evidence=action.evidence,
                risk_level=risk_level,
                needs_user_confirmation=needs_confirmation,
            )
        )

    return ValidatedPlan(
        request_summary=plan.request_summary,
        source_root=source_root,
        destination_root=destination_root,
        mode=plan.mode,
        requires_approval=True,
        global_reasoning=plan.global_reasoning,
        actions=validated_actions,
        questions=plan.questions,
        warnings=plan.warnings,
    )


def _repair_plan(
    provider: AIProvider,
    original_messages: list[dict[str, str]],
    bad_json: dict[str, Any],
    error: Exception,
) -> OrganizationPlan:
    repair_messages = [
        *original_messages,
        {
            "role": "user",
            "content": REPAIR_PROMPT.format(
                error=str(error),
                bad_json=json.dumps(bad_json, indent=2),
            ),
        },
    ]
    try:
        repaired = provider.generate_structured(repair_messages, PLAN_JSON_SCHEMA, "organization_plan")
        return OrganizationPlan.from_dict(repaired)
    except (PlanValidationError, ProviderError, ValueError, TypeError) as repair_exc:
        raise AgentPlanningError(
            f"AI returned invalid organization JSON and repair failed: {repair_exc}"
        ) from repair_exc


def _resolve_source(value: str, source_root: Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = source_root / candidate
    resolved = candidate.resolve()
    if not is_inside(resolved, source_root):
        raise PlanValidationError(f"Source path escapes source root: {value}")
    return resolved


def _resolve_destination(value: str, destination_root: Path, allow_outside_destination: bool) -> Path:
    raw = Path(value).expanduser()
    if raw.is_absolute():
        resolved = raw.resolve()
        if not allow_outside_destination and not is_inside(resolved, destination_root):
            raise PlanValidationError(f"Destination escapes allowed root: {value}")
        return resolved
    if ".." in raw.parts:
        raise PlanValidationError(f"Destination contains path traversal: {value}")
    safe_relative = sanitize_relative_path(value)
    resolved = (destination_root / safe_relative).resolve()
    if not allow_outside_destination and not is_inside(resolved, destination_root):
        raise PlanValidationError(f"Destination escapes allowed root: {value}")
    return resolved


def _all_source_paths(source_root: Path) -> set[Path]:
    paths: set[Path] = set()
    for candidate in source_root.rglob("*"):
        if candidate.is_file() or candidate.is_dir() or candidate.is_symlink():
            paths.add(candidate.resolve())
    return paths

