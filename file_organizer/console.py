from __future__ import annotations

import os
import sys
from pathlib import Path


class Style:
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"
    cyan = "\033[36m"
    green = "\033[32m"
    yellow = "\033[33m"
    red = "\033[31m"
    blue = "\033[34m"
    magenta = "\033[35m"


def color(text: str, style: str) -> str:
    if not _supports_color():
        return text
    return f"{style}{text}{Style.reset}"


def heading(text: str) -> str:
    return color(text, Style.bold + Style.cyan)


def label(text: str) -> str:
    return color(text, Style.bold)


def muted(text: str) -> str:
    return color(text, Style.dim)


def status(text: str, tone: str = "blue") -> str:
    styles = {
        "blue": Style.blue,
        "green": Style.green,
        "yellow": Style.yellow,
        "red": Style.red,
        "magenta": Style.magenta,
    }
    return color(text, Style.bold + styles.get(tone, Style.blue))


def shorten_path(path: Path, home: Path | None = None) -> str:
    home = home or Path.home()
    try:
        return "~/" + str(path.resolve().relative_to(home.resolve()))
    except ValueError:
        return str(path)


def rule(width: int = 78) -> str:
    return muted("-" * width)


def _supports_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()
