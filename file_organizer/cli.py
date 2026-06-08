from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .agent.loop import AgentLoop, deterministic_basic_plan
from .agent.memory import NaturalLanguageMemory, default_memory_path
from .agent.planner import validate_plan
from .auth import load_dotenv
from .core.reports import write_report
from .providers import ProviderConfig, create_provider
from .providers.base import ProviderUnavailable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-agent-driven folder organizer with preview-first safety.")
    parser.add_argument("target", nargs="?", help="Folder to organize. If omitted, interactive agent mode asks what to do.")
    parser.add_argument("--interactive", action="store_true", help="Run a continuous natural-language agent session.")
    parser.add_argument("--apply", action="store_true", help="Apply the approved AI plan after preview validation.")
    parser.add_argument("--provider", choices=["openai", "openai-compatible", "ollama"], help="AI provider.")
    parser.add_argument("--ai-provider", choices=["openai", "openai-compatible", "ollama"], help=argparse.SUPPRESS)
    parser.add_argument("--model", help="Model name.")
    parser.add_argument("--base-url", help="Provider base URL for compatible APIs or Ollama.")
    parser.add_argument("--ai-timeout", type=int, default=30, help="AI provider timeout in seconds.")
    parser.add_argument("--max-files", "--ai-max-files", dest="max_files", type=int, default=200, help="Maximum files to inspect.")
    parser.add_argument("--recursive", action="store_true", help="Scan subfolders.")
    parser.add_argument("--include-hidden", action="store_true", help="Allow hidden files to be scanned.")
    parser.add_argument("--destination", "--output", dest="destination", help="Destination root. Defaults to TARGET/Organized.")
    parser.add_argument("--no-memory", action="store_true", help="Do not read or write natural-language memory.")
    parser.add_argument("--memory-file", default=str(default_memory_path()), help="Natural-language memory JSON file.")
    parser.add_argument("--env-file", default=".env", help="Optional .env file to load.")
    parser.add_argument("--auth-status", action="store_true", help="Show AI provider auth status and exit.")
    parser.add_argument("--no-report", action="store_true", help="Do not write JSON/Markdown reports.")
    parser.add_argument(
        "--deterministic-basic",
        action="store_true",
        help="Emergency non-agent mode: move files into Review only. Off by default.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_dotenv(args.env_file)
    provider_name = args.provider or args.ai_provider or _env_provider()
    provider_config = ProviderConfig(
        provider=provider_name,
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.ai_timeout,
    )

    try:
        provider = create_provider(provider_config)
    except ProviderUnavailable as exc:
        print(f"AI provider unavailable, cannot create semantic organization plan. {exc}")
        return 2

    if args.auth_status:
        for key, value in provider.auth_status().items():
            print(f"{key}: {value}")
        return 0

    target = Path(args.target).expanduser().resolve() if args.target else None
    destination = Path(args.destination).expanduser().resolve() if args.destination else None

    if args.deterministic_basic:
        if target is None:
            parser.error("target is required for --deterministic-basic")
        destination_root = destination or target / "Organized"
        plan = deterministic_basic_plan(target, destination_root)
        validated = validate_plan(plan, target, destination_root)
        print("deterministic-basic mode is not AI-agent mode. It stages files into Review only.")
        loop = AgentLoop(provider, NaturalLanguageMemory(Path(args.memory_file)), args.max_files)
        loop._print_plan(validated)
        if args.apply:
            from .agent.executor import apply_plan

            result = apply_plan(validated, apply=True)
        else:
            result = {"applied": 0, "skipped": 0, "errors": [], "warnings": []}
            print("No files were changed.")
        if not args.no_report:
            write_report(validated, result, "deterministic-basic", provider.config.provider, provider.config.model, 0, 0)
        return 2 if result.get("errors") else 0

    memory = NaturalLanguageMemory(Path(args.memory_file))
    interactive = args.interactive or target is None
    if interactive:
        if not sys.stdin.isatty() and target is None:
            parser.error("target folder is required in non-interactive mode")
        exit_code = 0
        while True:
            try:
                request = input("file-organizer> ").strip()
            except EOFError:
                break
            if not request:
                break
            loop = AgentLoop(
                provider,
                memory,
                max_files=args.max_files,
                recursive=args.recursive,
                include_hidden=args.include_hidden,
                no_memory=args.no_memory,
            )
            exit_code = loop.run(
                request,
                target,
                destination,
                apply=args.apply,
                write_reports=not args.no_report,
                prompt_for_approval=True,
            )
            if target is not None:
                break
        return exit_code

    request = f"Organize {target}"
    loop = AgentLoop(
        provider,
        memory,
        max_files=args.max_files,
        recursive=args.recursive,
        include_hidden=args.include_hidden,
        no_memory=args.no_memory,
    )
    return loop.run(
        request,
        target,
        destination,
        apply=args.apply,
        write_reports=not args.no_report,
        prompt_for_approval=not args.apply,
    )


def _env_provider() -> str:
    import os

    return os.getenv("AI_PROVIDER", "openai")


if __name__ == "__main__":
    raise SystemExit(main())

