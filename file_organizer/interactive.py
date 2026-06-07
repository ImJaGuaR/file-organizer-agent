from __future__ import annotations

import re
import sys
from argparse import Namespace
from pathlib import Path

from .console import heading, label, muted, rule, status


def configure_from_prompt(args: Namespace) -> bool:
    if not sys.stdin.isatty():
        return False

    print(heading("File Organizer Agent"))
    print(muted("Tell the agent what folder to organize and how brave it should be."))
    print(muted("Example: organize my Downloads with LM Studio AI, create folders if needed, show plan"))
    request = input("> ").strip()
    if not request:
        return False

    target = _resolve_target(request)
    while target is None:
        answer = input("Which folder should I organize? ").strip()
        target = _resolve_target(answer) or Path(answer).expanduser()

    args.target = str(target)
    lower = request.lower()

    args.use_ai = args.use_ai or _has_any(lower, [" ai", "smart", "model", "lm studio", "llm"])
    args.ai_provider = args.ai_provider or ("openai-compatible" if "lm studio" in lower else args.ai_provider)
    args.ai_scope = args.ai_scope or ("all" if args.use_ai or _has_any(lower, ["all files", "every file", "everything", "move all"]) else "smart")
    args.ai_prefer = args.ai_prefer or _has_any(lower, ["prefer ai", "ai decide", "smarter", "smart"])
    args.ai_custom_folders = args.ai_custom_folders or _has_any(
        lower,
        [
            "create folder",
            "create folders",
            "new folder",
            "new folders",
            "no appropriate",
            "no apropriate",
            "appropriate folder",
            "apropriate folder",
            "if needed",
        ],
    )
    if args.ai_custom_folders:
        args.use_ai = True
        args.ai_scope = args.ai_scope or "all"
        args.ai_prefer = True
    args.recursive = args.recursive or _has_any(lower, ["subfolder", "subfolders", "recursive", "inside folders"])
    if args.output is None and _has_any(lower, ["under my user", "under my users", "under my home", "home folder"]):
        args.output = str(Path.home() / "Organized Files")

    if args.auto_apply_min_confidence is None and _has_any(lower, ["automatically", "by itself", "autonomous"]):
        args.auto_apply_min_confidence = 0.80

    wants_move = _has_any(lower, ["move", "apply", "do it", "act", "organize it", "organize them"])
    wants_preview = _has_any(lower, ["preview", "dry run", "show plan", "plan only"])
    args.apply = args.apply or (wants_move and not wants_preview and args.auto_apply_min_confidence is None)

    _print_interactive_summary(args)
    if args.apply:
        answer = input("This will move files. Continue? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            args.apply = False
            print("Okay, I will show a dry-run plan instead.")
    return True


def _resolve_target(text: str) -> Path | None:
    lower = text.lower()
    home = Path.home()
    if "download" in lower:
        return home / "Downloads"
    if "desktop" in lower:
        return home / "Desktop"
    if "document" in lower:
        return home / "Documents"
    if "sample" in lower or "demo" in lower:
        return Path("sample_messy_folder")

    match = re.search(r"(?:folder|directory|path)\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        candidate = match.group(1).strip().strip("\"'")
        if candidate:
            return Path(candidate).expanduser()

    stripped = text.strip().strip("\"'")
    if stripped.startswith(("~", "/", ".")):
        return Path(stripped).expanduser()
    return None


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _print_interactive_summary(args: Namespace) -> None:
    mode = "Move files after confirmation" if args.apply else "Preview plan only"
    intelligence = _intelligence_label(args)
    folder_strategy = (
        "Create purpose-based folders when needed"
        if args.ai_custom_folders
        else "Use built-in categories and safe Review fallback"
    )

    print()
    print(heading("Agent Setup"))
    print(rule())
    print(f"{label('Target')}          {args.target}")
    print(f"{label('Output')}          {args.output or 'inside target folder: Organized'}")
    print(f"{label('Mode')}            {status(mode, 'green' if args.apply else 'yellow')}")
    print(f"{label('Intelligence')}    {intelligence}")
    print(f"{label('Folders')}         {folder_strategy}")
    if args.use_ai:
        print(f"{label('Decision style')}  AI labels first, rules as safety net" if args.ai_prefer else f"{label('Decision style')}  Rules first, AI assists")
    if args.auto_apply_min_confidence is not None:
        print(f"{label('Autonomy')}        Auto-apply only above {args.auto_apply_min_confidence:.2f} confidence")
    print(rule())
    print()


def _intelligence_label(args: Namespace) -> str:
    if not args.use_ai:
        return "Fast local rules"
    provider = args.ai_provider or "configured AI provider"
    if provider == "openai-compatible":
        provider = "LM Studio / OpenAI-compatible AI"
    elif provider == "openai":
        provider = "OpenAI API"
    elif provider == "ollama":
        provider = "Ollama local AI"
    scope = "all files" if (args.ai_scope or "smart") == "all" else "content-heavy files"
    return f"{provider}, {scope}"
