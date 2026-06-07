from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ai_labeler import AILabeler
from .auth import load_dotenv, masked
from .classifier import choose_final_classification, classify_with_rules
from .config import DEFAULT_OUTPUT_FOLDER, default_memory_path
from .interactive import configure_from_prompt
from .memory import OrganizerMemory
from .models import Classification, OrganizationReport
from .mover import ensure_output_folders, execute_plan
from .planner import build_move_plan
from .reporter import print_plan, write_reports
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

    if args.interactive or not args.target:
        configured = configure_from_prompt(args)
        if not configured and not args.target:
            if sys.stdin.isatty():
                parser.error("target folder is required")
            parser.error("target folder is required in non-interactive mode")

    target_folder = Path(args.target).expanduser().resolve()
    if not target_folder.exists() or not target_folder.is_dir():
        parser.error(f"target folder does not exist or is not a directory: {target_folder}")

    output_folder = Path(args.output).expanduser().resolve() if args.output else target_folder / DEFAULT_OUTPUT_FOLDER
    output_folder = output_folder.resolve()

    signals = scan_folder(
        target_folder=target_folder,
        output_folder=output_folder,
        recursive=args.recursive,
        include_hidden=args.include_hidden,
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
    apply_changes = args.apply
    if not apply_changes and args.auto_apply_min_confidence is not None:
        apply_changes = _can_auto_apply(actions, args.auto_apply_min_confidence)
        if apply_changes:
            print(f"Auto-apply enabled: all planned moves met confidence >= {args.auto_apply_min_confidence:.2f}.")
        else:
            print(
                "Auto-apply skipped: at least one file was low-confidence, uncertain, "
                "or classified for Review."
            )
    if apply_changes:
        ensure_output_folders(output_folder)
    errors = execute_plan(actions, apply=apply_changes)
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
        },
    )
    print_plan(actions, dry_run=not apply_changes)

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
