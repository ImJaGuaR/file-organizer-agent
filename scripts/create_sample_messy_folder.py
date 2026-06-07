from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path("sample_messy_folder")
    root.mkdir(exist_ok=True)
    files = {
        "Project Milestone 1 notes.txt": "Operating Systems assignment milestone. Abstract, methodology, references.",
        "research-paper-summary.md": "# Research Paper\nThis document contains citations and literature review notes.",
        "OS final assignment instructions.pdf": "fake pdf placeholder with assignment rubric and deadline",
        "Machine Learning literature review.docx": "fake docx placeholder",
        "Thesis references.bib": "@article{example,title={Agentic file organization}}",
        "lecture_slides_week_04.pptx": "fake presentation placeholder",
        "invoice_april_2026.pdf": "fake invoice placeholder",
        "bank_statement_may.csv": "date,description,amount\n2026-05-01,Coffee,-4.50\n",
        "meeting_notes_team_alpha.txt": "Team Alpha meeting notes. Action items, owner, deadline.",
        "todo-personal.txt": "buy groceries\nrenew gym membership\ncall landlord\n",
        "screenshot_2026-06-07.png": "fake image placeholder",
        "Screenshot 2026-06-01 at 10.45.22.png": "fake image placeholder",
        "system_architecture_diagram.svg": "<svg><text>File organizer architecture</text></svg>",
        "uml_agent_flowchart.png": "fake image placeholder",
        "vacation_photo.jpg": "fake image placeholder",
        "family_photo.heic": "fake image placeholder",
        "profile_picture.webp": "fake image placeholder",
        "budget.xlsx": "fake spreadsheet placeholder",
        "grades_semester.xlsx": "fake spreadsheet placeholder",
        "data_export.csv": "name,score\nJulius,100\n",
        "experiment_results.json": "{\"experiment\":\"scheduler\",\"accuracy\":0.92}",
        "server_config.yaml": "host: localhost\nport: 8080\n",
        "database_dump.sql": "CREATE TABLE files(id INTEGER PRIMARY KEY, name TEXT);",
        "main.py": "def hello():\n    print('hello from code')\n",
        "organizer_agent.ts": "export function classify(name: string) { return name; }\n",
        "index.html": "<html><body>Portfolio draft</body></html>",
        "styles.css": "body { font-family: system-ui; }\n",
        "run_tests.sh": "python -m pytest\n",
        "notebook_analysis.ipynb": "{\"cells\": [], \"metadata\": {}, \"nbformat\": 4, \"nbformat_minor\": 5}",
        "archive.zip": "fake archive placeholder",
        "old_project_backup.tar.gz": "fake archive placeholder",
        "photos_backup.7z": "fake archive placeholder",
        "lecture_audio.mp3": "fake audio placeholder",
        "voice_memo_project_idea.m4a": "fake audio placeholder",
        "screen_recording_demo.mov": "fake video placeholder",
        "presentation_recording.mp4": "fake video placeholder",
        "unknownfile.weird": "unknown content",
        "mystery_no_extension": "unknown content without useful extension",
        "random_download.tmp": "temporary download fragment",
        "README copy 2.md": "# Duplicate-ish README\nNotes for a copied readme.",
    }
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")
    print(f"Created sample messy folder: {root.resolve()}")


if __name__ == "__main__":
    main()
