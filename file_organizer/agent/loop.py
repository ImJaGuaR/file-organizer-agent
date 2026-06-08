from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from file_organizer.core.paths import display_path, sanitize_relative_path, unique_destination
from file_organizer.core.reports import write_report
from file_organizer.core.scanner import scan_directory
from file_organizer.providers.base import AIProvider, ProviderError

from .executor import apply_plan
from .memory import NaturalLanguageMemory
from .planner import AgentPlanningError, propose_plan, revise_plan, validate_plan
from .prompts import INTENT_SYSTEM_PROMPT
from .schemas import OrganizationPlan, PLAN_JSON_SCHEMA, PlanAction, PlanValidationError, ValidatedPlan


INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_paths", "destination_root", "recursive", "include_hidden", "request_summary"],
    "properties": {
        "source_paths": {"type": "array", "items": {"type": "string"}},
        "destination_root": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "recursive": {"type": "boolean"},
        "include_hidden": {"type": "boolean"},
        "request_summary": {"type": "string"},
    },
}


class AgentLoop:
    def __init__(
        self,
        provider: AIProvider,
        memory: NaturalLanguageMemory,
        max_files: int = 200,
        recursive: bool = False,
        include_hidden: bool = False,
        no_memory: bool = False,
    ):
        self.provider = provider
        self.memory = memory
        self.max_files = max_files
        self.recursive = recursive
        self.include_hidden = include_hidden
        self.no_memory = no_memory
        self.user_edits: list[str] = []
        self.memory_updates: list[str] = []
        self.confirmed_high_risk_ids: set[int] = set()

    def run(
        self,
        request: str,
        target: Path | None,
        destination: Path | None,
        apply: bool,
        write_reports: bool = True,
        prompt_for_approval: bool = True,
    ) -> int:
        try:
            source_root, destination_root, recursive, include_hidden = self._resolve_roots(
                request,
                target,
                destination,
            )
        except ProviderError as exc:
            print(f"AI provider unavailable, cannot create semantic organization plan. {exc}")
            return 2

        print(f"I will inspect {source_root}. I will not move or delete anything until approval.")
        files = scan_directory(
            source_root,
            recursive=recursive,
            max_files=self.max_files,
            include_hidden=include_hidden,
            output_root=destination_root,
        )
        previewed = sum(1 for file in files if file.preview)
        memory_text = "(Memory disabled.)" if self.no_memory else self.memory.active_text()
        constraints = {
            "preview_first": True,
            "approval_required": True,
            "max_files": self.max_files,
            "recursive": recursive,
            "include_hidden": include_hidden,
            "destination_must_stay_inside": str(destination_root),
            "delete_behavior": "Move approved deletes into _To_Delete_Review; never permanently delete.",
        }
        try:
            plan = propose_plan(
                self.provider,
                request,
                files,
                memory_text,
                source_root,
                destination_root,
                constraints,
            )
            validated = validate_plan(plan, source_root, destination_root)
        except (AgentPlanningError, PlanValidationError, ProviderError) as exc:
            print(f"AI provider unavailable, cannot create semantic organization plan. {exc}")
            return 2

        self._print_plan(validated)
        result: dict[str, object] = {"applied": 0, "skipped": 0, "errors": [], "warnings": []}
        approved = apply
        if prompt_for_approval and not approved:
            validated = self._approval_loop(request, validated)
            approved = validated.mode == "apply"
        if approved:
            high_risk = {action.id for action in validated.actions if action.risk_level == "high"}
            confirmed_high_risk = high_risk if apply else self.confirmed_high_risk_ids
            result = apply_plan(validated, apply=True, confirmed_high_risk_ids=confirmed_high_risk)
            self._print_result(result)
        else:
            print("No files were changed.")

        if write_reports:
            json_path, md_path = write_report(
                validated,
                result,
                request,
                self.provider.config.provider,
                self.provider.config.model,
                len(files),
                previewed,
                self.user_edits,
                self.memory_updates,
            )
            print(f"Reports written:\n- {json_path}\n- {md_path}")
        return 2 if result.get("errors") else 0

    def _resolve_roots(
        self,
        request: str,
        target: Path | None,
        destination: Path | None,
    ) -> tuple[Path, Path, bool, bool]:
        if target is not None:
            source_root = target.expanduser().resolve()
            destination_root = destination.expanduser().resolve() if destination else source_root / "Organized"
            return source_root, destination_root, self.recursive, self.include_hidden

        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract source folders and options from this request. "
                    "Use absolute paths or ~ paths when the user names common folders.\n\n"
                    f"Request: {request}"
                ),
            },
        ]
        intent = self.provider.generate_structured(messages, INTENT_SCHEMA, "organizer_intent")
        source_paths = intent.get("source_paths") or []
        if not source_paths:
            raise ProviderError("The model did not choose a folder to inspect.")
        source_root = Path(source_paths[0]).expanduser().resolve()
        destination_value = intent.get("destination_root")
        destination_root = Path(destination_value).expanduser().resolve() if destination_value else source_root / "Organized"
        recursive = bool(intent.get("recursive", self.recursive)) or self.recursive
        include_hidden = bool(intent.get("include_hidden", self.include_hidden)) or self.include_hidden
        return source_root, destination_root, recursive, include_hidden

    def _approval_loop(self, request: str, validated: ValidatedPlan) -> ValidatedPlan:
        print("Type APPLY to apply, EDIT <id> <new destination>, SKIP <id>, DELETE <id>, WHY <id>, RESCAN, MEMORY, FORGET MEMORY, HELP, or CANCEL.")
        while True:
            try:
                raw = input("> ").strip()
            except EOFError:
                return validated
            if not raw:
                return validated
            command, _, rest = raw.partition(" ")
            upper = command.upper()
            if upper == "APPLY":
                high_risk = [action.id for action in validated.actions if action.risk_level == "high" and action.action != "skip"]
                if high_risk:
                    print(f"High-risk actions need extra confirmation: {', '.join(map(str, high_risk))}")
                    try:
                        confirmation = input("Type CONFIRM HIGH RISK to include them, or press Enter to skip them: ").strip()
                    except EOFError:
                        confirmation = ""
                    if confirmation == "CONFIRM HIGH RISK":
                        self.confirmed_high_risk_ids.update(high_risk)
                return replace(validated, mode="apply")
            if upper == "CANCEL":
                return replace(validated, mode="preview")
            if upper == "HELP":
                self._print_help()
                continue
            if upper == "WHY":
                self._why(validated, rest)
                continue
            if upper == "EDIT":
                validated = self._edit(validated, rest)
                self._print_plan(validated)
                continue
            if upper == "SKIP":
                validated = self._change_action(validated, rest, "skip")
                self._print_plan(validated)
                continue
            if upper == "DELETE":
                validated = self._change_action(validated, rest, "delete")
                self._print_plan(validated)
                continue
            if upper == "MEMORY":
                print(self.memory.active_text())
                continue
            if upper == "FORGET" and rest.upper() == "MEMORY":
                self.memory.forget_all()
                print("Memory forgotten.")
                continue
            if upper == "RESCAN":
                print("Use a new request to rescan; no files were changed.")
                continue
            validated = self._natural_revision(request, validated, raw)
            self._print_plan(validated)

    def _natural_revision(self, request: str, validated: ValidatedPlan, revision: str) -> ValidatedPlan:
        memory_text = "(Memory disabled.)" if self.no_memory else self.memory.active_text()
        try:
            revised = revise_plan(self.provider, request, revision, validated.to_plan(), memory_text)
            updated = validate_plan(revised, validated.source_root, validated.destination_root)
        except (AgentPlanningError, PlanValidationError, ProviderError) as exc:
            print(f"I could not revise the plan safely: {exc}")
            return validated
        if not self.no_memory:
            note = self.memory.add(f"User correction/preference: {revision}", "user_correction")
            self.memory_updates.append(note.text)
        self.user_edits.append(revision)
        return updated

    def _edit(self, validated: ValidatedPlan, rest: str) -> ValidatedPlan:
        action_id_text, _, destination_text = rest.strip().partition(" ")
        try:
            action_id = int(action_id_text)
            relative = sanitize_relative_path(destination_text)
        except (ValueError, TypeError) as exc:
            print(f"Could not edit action: {exc}")
            return validated
        reserved = {
            action.destination_path
            for action in validated.actions
            if action.destination_path is not None and action.id != action_id
        }
        actions = []
        for action in validated.actions:
            if action.id != action_id:
                actions.append(action)
                continue
            destination = unique_destination(validated.destination_root / relative / action.source_path.name, reserved)
            actions.append(
                replace(
                    action,
                    action="move",
                    destination_path=destination,
                    reasoning="User edited this destination.",
                    needs_user_confirmation=True,
                )
            )
        note_text = f"User prefers {destination_text.strip()} for files like action {action_id} when appropriate."
        if not self.no_memory:
            note = self.memory.add(note_text, "user_correction")
            self.memory_updates.append(note.text)
        self.user_edits.append(f"EDIT {action_id} {destination_text.strip()}")
        return replace(validated, actions=actions)

    def _change_action(self, validated: ValidatedPlan, rest: str, action_kind: str) -> ValidatedPlan:
        try:
            action_id = int(rest.strip())
        except ValueError:
            print("Please provide an action id.")
            return validated
        actions = []
        for action in validated.actions:
            if action.id == action_id:
                actions.append(
                    replace(
                        action,
                        action=action_kind,
                        destination_path=None,
                        risk_level="high" if action_kind == "delete" else action.risk_level,
                        needs_user_confirmation=True,
                        reasoning=f"User marked this action as {action_kind}.",
                    )
                )
            else:
                actions.append(action)
        if not self.no_memory:
            note = self.memory.add(f"User marked action {action_id} as {action_kind}.", "user_correction")
            self.memory_updates.append(note.text)
        self.user_edits.append(f"{action_kind.upper()} {action_id}")
        return replace(validated, actions=actions)

    def _why(self, validated: ValidatedPlan, rest: str) -> None:
        try:
            action_id = int(rest.strip())
        except ValueError:
            print("Please provide an action id.")
            return
        for action in validated.actions:
            if action.id == action_id:
                print(action.reasoning)
                if action.evidence:
                    print("Evidence:")
                    for item in action.evidence:
                        print(f"- {item}")
                return
        print(f"No action with id {action_id}.")

    def _print_plan(self, plan: ValidatedPlan) -> None:
        print("\nProposed plan:")
        print(plan.global_reasoning)
        for warning in plan.warnings:
            print(f"Warning: {warning}")
        print()
        print(f"{'ID':>3}  {'ACTION':<6}  {'RISK':<6}  {'FROM':<34}  TO")
        print("-" * 96)
        for action in plan.actions:
            destination = display_path(action.destination_path) if action.destination_path else ""
            print(
                f"{action.id:>3}  {action.action.upper():<6}  {action.risk_level:<6}  "
                f"{display_path(action.source_path):<34}  {destination}"
            )
            print(f"     why: {action.reasoning}")
        print()

    def _print_result(self, result: dict[str, object]) -> None:
        if result.get("errors"):
            print("Apply finished with errors:")
            for error in result["errors"]:
                print(f"- {error}")
        else:
            print(f"Applied {result.get('applied', 0)} action(s).")
        for warning in result.get("warnings", []):
            print(f"Warning: {warning}")

    def _print_help(self) -> None:
        print("Commands: APPLY, CANCEL, WHY <id>, EDIT <id> <folder>, SKIP <id>, DELETE <id>, RESCAN, MEMORY, FORGET MEMORY, HELP.")


def deterministic_basic_plan(source_root: Path, destination_root: Path) -> OrganizationPlan:
    actions = []
    for index, path in enumerate(sorted(source_root.glob("*")), start=1):
        if not path.is_file() or path.name.startswith("."):
            continue
        actions.append(
            PlanAction(
                id=index,
                action="move",
                source_path=str(path.resolve()),
                destination_path=f"Review/{path.name}",
                confidence=0.1,
                reasoning="Emergency deterministic-basic mode puts files in Review without semantic classification.",
                evidence=["No AI semantic planning was used."],
                risk_level="medium",
                needs_user_confirmation=True,
            )
        )
    return OrganizationPlan(
        request_summary="Deterministic basic review move.",
        source_root=str(source_root),
        destination_root=str(destination_root),
        mode="preview",
        requires_approval=True,
        global_reasoning="This is not agent mode. Files are only staged into Review.",
        actions=actions,
        questions=[],
        warnings=["deterministic-basic is an emergency mode and does not semantically organize files."],
    )
