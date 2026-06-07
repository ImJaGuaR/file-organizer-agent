from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path("sample_messy_folder")
    root.mkdir(exist_ok=True)
    files = {
        "Project Milestone 1 notes.txt": "Operating Systems assignment milestone. Abstract, methodology, references.",
        "research-paper-summary.md": "# Research Paper\nThis document contains citations and literature review notes.",
        "screenshot_2026-06-07.png": "fake image placeholder",
        "vacation_photo.jpg": "fake image placeholder",
        "budget.xlsx": "fake spreadsheet placeholder",
        "data_export.csv": "name,score\nJulius,100\n",
        "main.py": "def hello():\n    print('hello from code')\n",
        "archive.zip": "fake archive placeholder",
        "lecture_audio.mp3": "fake audio placeholder",
        "unknownfile.weird": "unknown content",
    }
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    print(f"Created sample messy folder: {root.resolve()}")


if __name__ == "__main__":
    main()
