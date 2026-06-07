# File Organizer Agent

A simple AI-assisted agent that observes a messy folder, reasons about file categories, safely plans moves, acts only when approved, and writes a report.

The agent works without an API key using local rules. If you provide an OpenAI API key, it can also ask an AI model to improve labels for text-like files such as assignments, notes, code, CSV files, and research documents.

## Features

- Scans a selected folder and reads file metadata.
- Classifies documents, images, audio, videos, code, archives, spreadsheets, data, research, and unknown files.
- Reads safe short previews from text files, code files, CSV/JSON files, and DOCX files.
- Optionally uses OpenAI for structured AI labels.
- Creates a safe move plan before changing anything.
- Uses dry-run mode by default.
- Avoids overwriting files by renaming duplicates.
- Skips risky files and places uncertain files in `Review`.
- Writes JSON and Markdown reports.
- Supports simple memory rules for future corrections.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For running the tests:

```bash
pip install -r requirements-dev.txt
pytest
```

AI is optional. To enable OpenAI labeling:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

The default model is `gpt-5.4-mini`, chosen as a lower-cost model suitable for structured labeling. You can override it:

```bash
export OPENAI_MODEL="gpt-5.4-mini"
```

## Quick Demo

Create a fake messy folder:

```bash
python scripts/create_sample_messy_folder.py
```

Preview what the agent would do:

```bash
python -m file_organizer sample_messy_folder
```

Preview with AI labeling:

```bash
python -m file_organizer sample_messy_folder --use-ai
```

Actually organize the sample folder:

```bash
python -m file_organizer sample_messy_folder --apply
```

## Real Folder Usage

Always preview first:

```bash
python -m file_organizer ~/Downloads
```

Then apply only when the plan looks correct:

```bash
python -m file_organizer ~/Downloads --apply
```

## Memory Rules

You can teach the agent simple extension rules:

```bash
python -m file_organizer --learn-extension .ipynb Code/Notebooks
```

Then future runs will use that saved rule.

## Output Structure

By default, files are moved into an `Organized` folder inside the selected folder:

```text
Organized/
  Documents/
    PDFs/
    Word/
    Text/
    Presentations/
  Images/
    Screenshots/
    Photos/
    Diagrams/
    Other/
  Code/
  Data/
    Spreadsheets/
    CSV/
    JSON/
  Archives/
  Audio/
  Videos/
  Research/
  Review/
  Reports/
```

## Safety

The agent never moves files unless you pass `--apply`. It also avoids overwriting by generating names like `file (1).pdf` when a destination already exists.

## OpenAI API Notes

This project uses the OpenAI Responses API through the official Python SDK. The API key is read from `OPENAI_API_KEY`; it is not stored in this project.

The AI labeling module sends only file metadata and a short text preview, not the whole folder. It asks the model to return structured JSON with:

- category
- subfolder
- confidence
- summary
- reason

The agent then compares the AI label with the local rule label. High-confidence AI labels can improve the destination folder; low-confidence AI labels are ignored.
