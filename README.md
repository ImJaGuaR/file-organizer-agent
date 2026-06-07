# File Organizer Agent

A simple AI-assisted agent that observes a messy folder, reasons about file categories, safely plans moves, acts only when approved, and writes a report.

The agent works without an API key using local rules. If you provide AI credentials, it can also ask a model to improve labels for text-like files such as assignments, notes, code, CSV files, and research documents.

## Features

- Scans a selected folder and reads file metadata.
- Classifies documents, images, audio, videos, code, archives, spreadsheets, data, research, and unknown files.
- Reads safe short previews from text files, code files, CSV/JSON files, and DOCX files.
- Optionally uses OpenAI, OpenAI-compatible APIs, or local Ollama for structured AI labels.
- Organizes by purpose first when possible, then file type. For example, a voice memo about a project idea goes to `Ideas/Audio`, not only `Audio`.
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

AI is optional. The safest setup is to copy the example environment file and add your own key locally:

```bash
cp .env.example .env
```

Do not commit `.env`; it is ignored by Git.

### Option 1: OpenAI API

```bash
export OPENAI_API_KEY="your_api_key_here"
export AI_PROVIDER="openai"
```

The default model is `gpt-5.4-mini`, chosen as a lower-cost model suitable for structured labeling. You can override it:

```bash
export OPENAI_MODEL="gpt-5.4-mini"
```

### Option 2: Any OpenAI-Compatible API

Use this for providers that support a `/v1/chat/completions` style endpoint.

```bash
export AI_PROVIDER="openai-compatible"
export OPENAI_COMPATIBLE_API_KEY="your_provider_key"
export OPENAI_COMPATIBLE_BASE_URL="https://api.your-provider.com/v1"
export OPENAI_COMPATIBLE_MODEL="provider/model-name"
```

Then run:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible
```

For LM Studio, use the base URL and model name shown in the Developer tab. Example:

```bash
AI_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_BASE_URL=http://localhost:1234/v1
OPENAI_COMPATIBLE_API_KEY=lm-studio
OPENAI_COMPATIBLE_MODEL=google/gemma-4-26b-a4b
AI_TIMEOUT_SECONDS=30
```

Local models can be slower than cloud APIs. For a quick demo, ask AI to label only the first file and let rules handle the rest:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-max-files 1 --ai-timeout 20
```

To make the project more AI-heavy, send every scanned file to AI:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-timeout 30
```

For the clearest classroom demo, prefer AI labels whenever the model returns valid structured JSON:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-prefer --ai-timeout 30
```

Allow the AI to create new sanitized folder categories when the built-in categories do not fit:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-prefer --ai-custom-folders --ai-timeout 30
```

The planner creates missing folders automatically. AI folder names are sanitized before use, so unsafe path parts such as `..` are not allowed.

For a more autonomous run, let the agent apply the plan only if every planned move is confident and no file is sent to `Review`:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-prefer --ai-custom-folders --auto-apply-min-confidence 0.80 --ai-timeout 30
```

This is safer than blindly moving files because low-confidence files still stay in dry-run mode.

For slow local models, combine all-file AI with a limit while testing:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-max-files 3 --ai-timeout 30
```

### Option 3: Local Ollama

This option uses a local model and does not need an API key:

```bash
export AI_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1"
```

Then run:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider ollama
```

Check the current AI configuration:

```bash
python -m file_organizer --auth-status
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

## Interactive Agent Mode

Run without a target to describe the task in plain English:

```bash
python -m file_organizer
```

Example prompt:

```text
organize my Downloads with LM Studio AI, create folders if needed, and move the files under my home folder
```

The agent will interpret the request, show the target, output folder, AI settings, and whether it plans to move files. If the request would move files, it asks for confirmation first.
The interactive screen uses readable labels such as `Intelligence`, `Folder strategy`, and `Mode` instead of internal option names.

You can also force the prompt mode:

```bash
python -m file_organizer --interactive
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
  Ideas/
    Audio/
    Text/
  Finance/
    PDFs/
    CSV/
    Spreadsheets/
  Coursework/
    PDFs/
    Presentations/
  Meetings/
  Backups/
    Archives/
  Review/
  Reports/
```

## Safety

The agent never moves files unless you pass `--apply`. It also avoids overwriting by generating names like `file (1).pdf` when a destination already exists.

## AI Authentication Notes

This project does not reuse your Codex or ChatGPT login. The OpenAI API uses API keys for normal server-side authentication, so the key is read from `OPENAI_API_KEY` or `.env`; it is not stored in GitHub.

The AI labeling module sends only file metadata and a short text preview, not the whole folder. It asks the model to return structured JSON with:

- category
- subfolder
- confidence
- summary
- reason

The agent then compares the AI label with the local rule label. High-confidence AI labels can improve the destination folder; low-confidence AI labels are ignored.
