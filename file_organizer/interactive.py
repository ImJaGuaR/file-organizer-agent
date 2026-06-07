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
    target = Path(args.target).expanduser() if args.target else _resolve_target(request)
    while target is None:
        answer = input("Which folder should I organize? ").strip()
        target = _resolve_target(answer) or Path(answer).expanduser()

    args.target = str(target)
    lower = request.lower()

    args.use_ai = True
    args.ai_provider = args.ai_provider or ("openai-compatible" if "lm studio" in lower else args.ai_provider)
    args.ai_scope = args.ai_scope or "all"
    args.ai_prefer = True
    args.ai_custom_folders = True
    args.recursive = args.recursive or _has_any(lower, ["subfolder", "subfolders", "recursive", "inside folders"])
    if args.output is None:
        output = _resolve_output(request)
        if output is not None:
            args.output = str(output)

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


def _resolve_output(text: str) -> Path | None:
    lower = text.lower()
    home = Path.home()

    explicit_path = _extract_output_path(text)
    if explicit_path is not None:
        return explicit_path.expanduser()

    if _has_any(
        lower,
        [
            "to the user folder",
            "to user folder",
            "into the user folder",
            "inside the user folder",
            "under the user folder",
            "under my user",
            "under my users",
            "to my home",
            "into my home",
            "under my home",
            "home folder",
            "user home",
            "my user folder",
            "my home folder",
        ],
    ):
        return home

    if _has_any(lower, ["to desktop", "onto desktop", "desktop folder"]):
        return home / "Desktop"
    if _has_any(lower, ["to documents", "documents folder"]):
        return home / "Documents"
    return None


def _extract_output_path(text: str) -> Path | None:
    match = re.search(
        r"(?:output|destination|move(?: them| files)? to|put(?: them| files)? in|save(?: them| files)? to)\s+"
        r"((?:~|/|\.)\S+|\"[^\"]+\"|'[^']+')",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    candidate = match.group(1).strip().strip("\"'")
    if not candidate:
        return None
    return Path(candidate)


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
