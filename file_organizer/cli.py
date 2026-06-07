from __future__ import annotations

import argparse
from dataclasses import replace
import re
import sys
from pathlib import Path

from .ai_labeler import AILabeler
from .auth import load_dotenv, masked
from .classifier import choose_final_classification, classify_with_rules
from .config import DEFAULT_OUTPUT_FOLDER, default_memory_path
from .interactive import configure_from_prompt, configure_from_request, _resolve_output
from .memory import OrganizerMemory
from .models import Classification, OrganizationReport
from .mover import execute_plan
from .planner import build_delete_plan_from_paths, build_move_plan
from .reporter import print_apply_result, print_plan, write_reports
from .scanner import scan_folder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Observe, think, and act on a messy folder using safe file organization rules and optional AI labels."
    )
    parser.add_argument("target", nargs="?", help="Folder to organize.")
    parser.add_argument(
        "--output",
        help=f"Output folder. Defaults to TARGET/{DEFAULT_OUTPUT_FOLDER}.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this flag, the agent only prints a dry-run plan.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan subfolders too. The output folder is always excluded.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and folders.",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Use an AI provider for additional labeling.",
    )
    parser.add_argument(
        "--ai-provider",
        choices=["openai", "openai-compatible", "ollama"],
        help="AI provider. Defaults to AI_PROVIDER or openai.",
    )
    parser.add_argument(
        "--model",
        help="Model to use for AI labeling. Defaults depend on provider environment variables.",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for openai-compatible or ollama providers.",
    )
    parser.add_argument(
        "--ai-timeout",
        type=int,
        help="Seconds to wait for each AI request. Defaults to AI_TIMEOUT_SECONDS or 30.",
    )
    parser.add_argument(
        "--ai-max-files",
        type=int,
        help="Maximum number of files to send to AI in one run. Useful for slow local models.",
    )
    parser.add_argument(
        "--ai-scope",
        choices=["smart", "all"],
        help="Choose which files AI labels. smart uses AI for content-heavy files; all sends every file.",
    )
    parser.add_argument(
        "--ai-prefer",
        action="store_true",
        help="Prefer parsed AI labels over rule labels. Good for demonstrating a more AI-heavy agent.",
    )
    parser.add_argument(
        "--ai-custom-folders",
        action="store_true",
        help="Allow AI to create sanitized custom top-level folders when normal categories do not fit.",
    )
    parser.add_argument(
        "--auto-apply-min-confidence",
        type=float,
        help="Automatically apply the plan only if every move has at least this confidence and no file is in Review.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional .env file to load before reading API settings.",
    )
    parser.add_argument(
        "--auth-status",
        action="store_true",
        help="Show AI provider authentication status and exit.",
    )
    parser.add_argument(
        "--memory-file",
        default=str(default_memory_path()),
        help="JSON memory file for learned classification rules.",
    )
    parser.add_argument(
        "--learn-extension",
        nargs=2,
        metavar=("EXTENSION", "FOLDER"),
        help="Save an extension rule, for example: --learn-extension .ipynb Code/Notebooks",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write report files.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Ask what to do in natural language before running.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_dotenv(args.env_file)
    memory = OrganizerMemory(Path(args.memory_file))

    if args.auth_status:
        ai_labeler = AILabeler.from_environment(
            model=args.model,
            enabled=True,
            provider=args.ai_provider,
            base_url=args.base_url,
            timeout_seconds=args.ai_timeout,
            scope=args.ai_scope,
            allow_custom_folders=args.ai_custom_folders,
        )
        print("AI authentication status")
        print(f"- provider: {ai_labeler.provider}")
        print(f"- model: {ai_labeler.model}")
        print(f"- base_url: {ai_labeler.base_url or '(provider default)'}")
        if ai_labeler.provider == "openai":
            import os

            print(f"- OPENAI_API_KEY: {masked(os.getenv('OPENAI_API_KEY'))}")
        elif ai_labeler.provider == "openai-compatible":
            import os

            print(f"- OPENAI_COMPATIBLE_API_KEY: {masked(os.getenv('OPENAI_COMPATIBLE_API_KEY'))}")
        else:
            print("- API key: not needed")
        return 0

    if args.learn_extension:
        extension, folder = args.learn_extension
        memory.learn_extension(extension, folder)
        print(f"Saved memory rule: {extension} -> {folder}")
        return 0

    interactive_session = args.interactive or not args.target
    if interactive_session:
        configured = configure_from_prompt(args)
        if not configured and not args.target:
            if sys.stdin.isatty():
                parser.error("target folder is required")
            parser.error("target folder is required in non-interactive mode")

        exit_code = _run_configured(args, memory, parser)
        followups = list(getattr(args, "followup_requests", []))
        while followups or sys.stdin.isatty():
            if followups:
                next_request = followups.pop(0)
                print(f"\nNext queued task: {next_request}")
            else:
                try:
                    next_request = input("\nTell me another task, or press Enter to quit: ").strip()
                except EOFError:
                    break
                if not next_request:
                    break
            next_args = parser.parse_args([])
            _copy_session_options(args, next_args)
            configure_from_request(next_args, next_request)
            exit_code = _run_configured(next_args, memory, parser)
            followups.extend(getattr(next_args, "followup_requests", []))
        return exit_code

    return _run_configured(args, memory, parser)


def _copy_session_options(source: argparse.Namespace, target: argparse.Namespace) -> None:
    for name in [
        "env_file",
        "memory_file",
        "no_report",
        "ai_provider",
        "model",
        "base_url",
        "ai_timeout",
        "ai_max_files",
    ]:
        setattr(target, name, getattr(source, name))


def _run_configured(args: argparse.Namespace, memory: OrganizerMemory, parser: argparse.ArgumentParser) -> int:
    target_folder = Path(args.target).expanduser().resolve()
    if not target_folder.exists() or not target_folder.is_dir():
        parser.error(f"target folder does not exist or is not a directory: {target_folder}")

    task = getattr(args, "task", "organize")
    if task == "delete" and args.output is None:
        output_folder = Path.home() / ".file-organizer-agent"
    else:
        output_folder = Path(args.output).expanduser().resolve() if args.output else target_folder / DEFAULT_OUTPUT_FOLDER
    output_folder = output_folder.resolve()

    signals = (
        []
        if task == "delete"
        else scan_folder(
            target_folder=target_folder,
            output_folder=output_folder,
            recursive=args.recursive,
            include_hidden=args.include_hidden,
        )
    )
    ai_labeler = AILabeler.from_environment(
        model=args.model,
        enabled=args.use_ai,
        provider=args.ai_provider,
        base_url=args.base_url,
        timeout_seconds=args.ai_timeout,
        scope=args.ai_scope,
        allow_custom_folders=args.ai_custom_folders,
    )
    if task == "delete":
        actions = build_delete_plan_from_paths(_delete_targets(target_folder))
    else:
        classifications: dict[Path, Classification] = {}
        ai_calls_remaining = args.ai_max_files

        for signal in signals:
            rule_classification = classify_with_rules(signal, memory)
            if ai_calls_remaining is not None and ai_calls_remaining <= 0:
                ai_classification = None
            else:
                ai_classification = ai_labeler.classify(signal, rule_classification)
                if ai_classification is not None and ai_classification.source.startswith("ai-"):
                    ai_calls_remaining = None if ai_calls_remaining is None else ai_calls_remaining - 1
            classifications[signal.path] = choose_final_classification(
                rule_classification,
                ai_classification,
                prefer_ai=args.ai_prefer,
            )

        actions = build_move_plan(signals, classifications, output_folder)
    interactive_apply_prompt = bool(getattr(args, "interactive_apply_prompt", False))
    apply_changes = args.apply
    if not apply_changes and args.auto_apply_min_confidence is not None and not interactive_apply_prompt:
        apply_changes = _can_auto_apply(actions, args.auto_apply_min_confidence)
        if apply_changes:
            print(f"Auto-apply enabled: all planned moves met confidence >= {args.auto_apply_min_confidence:.2f}.")
        else:
            print(
                "Auto-apply skipped: at least one file was low-confidence, uncertain, "
                "or classified for Review."
            )
    errors = execute_plan(actions, apply=apply_changes)
    print_plan(
        actions,
        dry_run=not apply_changes,
        interactive_apply_prompt=interactive_apply_prompt and not apply_changes,
    )

    if interactive_apply_prompt and not apply_changes:
        while True:
            try:
                answer = input(
                    "\nSay APPLY, a correction like 'move all to Downloads', FIX 2 Folder/Subfolder, or Enter to quit: "
                ).strip()
            except EOFError:
                print("Okay, no files were moved.")
                break
            if answer == "APPLY":
                errors = execute_plan(actions, apply=True)
                apply_changes = True
                print_apply_result(errors)
                break
            if not answer:
                print("Okay, no files were moved.")
                break
            output_correction = _resolve_output_correction(answer)
            if output_correction is not None and task == "organize":
                output_folder = output_correction.resolve()
                actions = _retarget_move_actions(actions, output_folder)
                print(f"Okay, I updated the output folder to {output_folder}.")
                print_plan(actions, dry_run=True, interactive_apply_prompt=True)
                continue

            corrected_actions = _apply_interactive_correction(answer, actions, output_folder, memory)
            if corrected_actions is None:
                print("I did not understand yet. Try: move all to Downloads, move all to user folder, or FIX 2 Coursework/Text")
                continue
            actions = corrected_actions
            print_plan(actions, dry_run=True, interactive_apply_prompt=True)

    report = OrganizationReport(
        target_folder=target_folder,
        output_folder=output_folder,
        dry_run=not apply_changes,
        actions=actions,
        errors=errors,
        metadata={
            "ai_requested": args.use_ai,
            "ai_provider": ai_labeler.provider if args.use_ai else None,
            "ai_model": ai_labeler.model if args.use_ai else None,
            "ai_scope": ai_labeler.scope if args.use_ai else None,
            "ai_prefer": args.ai_prefer if args.use_ai else None,
            "ai_custom_folders": args.ai_custom_folders if args.use_ai else None,
            "auto_apply_min_confidence": args.auto_apply_min_confidence,
            "recursive": args.recursive,
            "task": task,
        },
    )

    if not args.no_report:
        json_path, md_path = write_reports(report)
        print(f"\nReports written:\n- {json_path}\n- {md_path}")

    if errors:
        return 2
    return 0


def _can_auto_apply(actions: list[object], min_confidence: float) -> bool:
    for action in actions:
        if action.action != "move":
            continue
        classification = action.classification
        if classification.category == "Review":
            return False
        if classification.confidence < min_confidence:
            return False
        if classification.source in {"ai-error", "ai-fallback", "ai-unavailable"}:
            return False
    return True


def _delete_targets(target_folder: Path) -> list[Path]:
    try:
        return sorted(target_folder.iterdir())
    except PermissionError:
        print(f"Cannot access {target_folder}. On macOS, give Terminal Full Disk Access to manage Trash.")
        return []
    except OSError as exc:
        print(f"Cannot read {target_folder}: {exc}")
        return []


def _resolve_output_correction(answer: str) -> Path | None:
    normalized = answer.strip()
    if normalized.upper().startswith("FIX ALL "):
        normalized = normalized[8:].strip()
    if normalized.upper().startswith("FIX "):
        normalized = normalized[4:].strip()
    return _resolve_output(normalized)


def _retarget_move_actions(actions: list[object], output_folder: Path) -> list[object]:
    reserved: set[Path] = set()
    retargeted = []
    for action in actions:
        if action.action != "move":
            retargeted.append(action)
            continue
        destination_dir = output_folder.joinpath(*action.classification.folder_parts)
        destination = _unique_destination(destination_dir / action.source.name, reserved)
        reserved.add(destination)
        retargeted.append(replace(action, destination=destination))
    return retargeted


def _unique_destination(destination: Path, reserved_destinations: set[Path]) -> Path:
    if destination not in reserved_destinations and not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination.parent / f"{destination.stem} ({counter}){destination.suffix}"
        if candidate not in reserved_destinations and not candidate.exists():
            return candidate
        counter += 1


def _apply_interactive_correction(
    answer: str,
    actions: list[object],
    output_folder: Path,
    memory: OrganizerMemory,
) -> list[object] | None:
    parts = answer.strip().split(maxsplit=2)
    if len(parts) != 3 or parts[0].upper() != "FIX":
        return None
    try:
        index = int(parts[1]) - 1
    except ValueError:
        return None
    if index < 0 or index >= len(actions):
        return None
    action = actions[index]
    if action.action != "move":
        return None

    folder = parts[2].strip().strip("\"'")
    category, subfolder = _split_folder(folder)
    if not category:
        return None

    corrected = Classification(
        category=category,
        subfolder=subfolder,
        confidence=1.0,
        reason="User correction saved to memory.",
        source="memory",
        summary=action.classification.summary,
    )
    destination = _corrected_destination(action.source, corrected, output_folder, actions, index)
    corrected_action = replace(
        action,
        destination=destination,
        classification=corrected,
        reason=corrected.reason,
    )
    memory.learn_name(action.source.name, _folder_text(category, subfolder))
    return [corrected_action if current_index == index else current for current_index, current in enumerate(actions)]


def _split_folder(folder: str) -> tuple[str, str | None]:
    parts = [_sanitize_folder_part(part) for part in folder.replace("\\", "/").split("/") if part.strip()]
    parts = [part for part in parts if part]
    if not parts:
        return "", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], "/".join(parts[1:])


def _folder_text(category: str, subfolder: str | None) -> str:
    return f"{category}/{subfolder}" if subfolder else category


def _sanitize_folder_part(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9 ._-]+", " ", value).strip(" ._-")
    value = re.sub(r"\s+", " ", value)
    if value in {"", ".", ".."}:
        return ""
    return value[:40]


def _corrected_destination(
    source: Path,
    classification: Classification,
    output_folder: Path,
    actions: list[object],
    corrected_index: int,
) -> Path:
    destination_dir = output_folder.joinpath(*classification.folder_parts)
    destination = destination_dir / source.name
    reserved = {
        action.destination
        for index, action in enumerate(actions)
        if index != corrected_index and getattr(action, "action", None) == "move"
    }
    if destination not in reserved and not destination.exists():
        return destination
    counter = 1
    while True:
        candidate = destination_dir / f"{destination.stem} ({counter}){destination.suffix}"
        if candidate not in reserved and not candidate.exists():
            return candidate
        counter += 1
