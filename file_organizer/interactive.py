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
    print(muted("Tell the agent which folder to organize. It will show a plan before moving anything."))
    print(muted("Example: organize the sample folder with AI labels, create folders if needed, and show the plan"))
    request = input("> ").strip()
    if not request:
        return False

    args.interactive_apply_prompt = True
    target = _resolve_target(request) or (Path(args.target).expanduser() if args.target else None)
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

    args.apply = False
    args.auto_apply_min_confidence = None

    _print_interactive_summary(args)
    return True


def _resolve_target(text: str) -> Path | None:
    lower = text.lower()
    home = Path.home()
    stripped = text.strip().strip("\"'")
    if stripped.startswith(("~", "/", ".")):
        return Path(stripped).expanduser()

    match = re.search(
        r"(?:folder|directory|path)\s+((?:~|/|\.)\S+|\"[^\"]+\"|'[^']+')",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip().strip("\"'")
        if candidate:
            return Path(candidate).expanduser()

    if "download" in lower:
        return home / "Downloads"
    if "desktop" in lower:
        return home / "Desktop"
    if "document" in lower:
        return home / "Documents"
    if "sample" in lower or "demo" in lower:
        return Path("sample_messy_folder")
    return None


def _has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _print_interactive_summary(args: Namespace) -> None:
    mode = "Move files after confirmation" if args.apply else "Preview plan only"
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
    print(f"{label('Folders')}         {folder_strategy}")
    print(rule())
    print()
