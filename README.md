# File Organizer Agent

A safe AI-first folder organizer that observes a messy folder, asks an AI model for purpose-based labels, validates the response, previews the move plan, and moves files only after approval.

Interactive mode is designed as an AI tool: it tries AI labels first for all files, then uses local rules only when the AI provider is unavailable, errors, or returns invalid JSON.

## Features

- Scans a selected folder and reads file metadata.
- Classifies documents, images, audio, videos, code, archives, spreadsheets, data, research, and unknown files.
- Reads safe short previews from text files, code files, CSV/JSON files, and DOCX files.
- Uses OpenAI, OpenAI-compatible APIs, or local Ollama for structured AI labels.
- Falls back to local rules when AI fails, so the organizer still produces a safe plan.
- Organizes by purpose first when possible, then file type. For example, a voice memo about a project idea goes to `Ideas/Audio`, not only `Audio`.
- Creates a safe move plan before changing anything.
- In interactive mode, type `APPLY` after previewing the plan to move files.
- Supports preview-first delete tasks, such as emptying a trash folder.
- Avoids overwriting files by renaming duplicates.
- Creates only the destination folders needed by the current plan.
- Learns filename corrections from interactive feedback and reuses them later.
- Skips risky files and places uncertain files in `Review`.
- Writes JSON and Markdown reports.
- Supports simple memory rules for future corrections.

## Supported Operating Systems

The project is pure Python and supports:

- macOS
- Linux
- Windows 10/11

Python 3.10 or newer is recommended.

## Installation Guide

First clone the repository:

```bash
git clone https://github.com/ImJaGuaR/file-organizer-agent.git
cd file-organizer-agent
```

If you already cloned it, update it with:

```bash
cd file-organizer-agent
git pull origin main
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
python -m file_organizer
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the app:

```bash
python -m file_organizer
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app:

```powershell
python -m file_organizer
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the virtual environment again.

### Windows Command Prompt

```bat
py -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python -m file_organizer
```

## AI Provider Setup

Interactive mode tries AI first. Configure one AI provider before running a real demo. If no AI provider is configured, the app still works, but it will show that AI was unavailable and use local rules as a fallback.

Create a local `.env` file in the project root. Do not commit `.env`; it is ignored by Git.

macOS/Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and fill in one provider.

### Option 1: OpenAI API

macOS/Linux:

```bash
cat > .env <<'EOF'
AI_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
EOF
```

Windows PowerShell:

```powershell
@"
AI_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
"@ | Set-Content .env
```

You can override the model:

```bash
OPENAI_MODEL=your_model_name
```

### Option 2: Any OpenAI-Compatible API

Use this for providers that support a `/v1/chat/completions` style endpoint.

macOS/Linux `.env` example:

```bash
cat > .env <<'EOF'
AI_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_provider_key
OPENAI_COMPATIBLE_BASE_URL=https://api.your-provider.com/v1
OPENAI_COMPATIBLE_MODEL=provider/model-name
AI_TIMEOUT_SECONDS=30
EOF
```

For LM Studio, use the base URL and model name shown in the Developer tab. Example:

```text
AI_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_BASE_URL=http://localhost:1234/v1
OPENAI_COMPATIBLE_API_KEY=lm-studio
OPENAI_COMPATIBLE_MODEL=google/gemma-4-26b-a4b
AI_TIMEOUT_SECONDS=60
```

Local models can be slower than cloud APIs. For direct CLI testing, you can limit AI calls:

```bash
python -m file_organizer sample_messy_folder --use-ai --ai-provider openai-compatible --ai-scope all --ai-prefer --ai-custom-folders --ai-max-files 5
```

The planner sanitizes AI folder names before use, so unsafe path parts such as `..` are not allowed.

### Option 3: Local Ollama

This option uses a local model and does not need an API key:

```bash
cat > .env <<'EOF'
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
EOF
```

Check the current AI configuration:

```bash
python -m file_organizer --auth-status
```

## Quick Demo

Create a fake messy folder:

macOS/Linux:

```bash
python scripts/create_sample_messy_folder.py
```

Windows:

```bash
python scripts/create_sample_messy_folder.py
```

Start interactive mode:

```bash
python -m file_organizer
```

Example prompt:

```text
organize the sample folder and create folders if needed
```

The app prints a preview plan first. To apply it, type:

```text
APPLY
```

## Interactive Agent Mode

Run without a target to describe the task in plain English:

```bash
python -m file_organizer
```

Example prompt:

```text
organize my Downloads and move into the user folder, do not create the Organized folder
```

The agent will:

- use AI labels first
- show the target folder
- choose the output folder from the prompt
- create purpose-based folders only when needed
- print a preview plan first

After the plan, type `APPLY` and press Enter to move the files in the same run. Press Enter without typing `APPLY` to leave the preview unchanged.

If the agent chooses the wrong folder, correct it before applying:

```text
FIX 2 Coursework/Text
FIX 4 Finance/Receipts
```

The number is the plan item number. The folder is the category/subfolder you want. The agent updates the plan, saves the correction for that filename, and will remember it in future runs.

Delete tasks use the same preview-first approval flow:

```text
delete trash in the trash can
empty trash can
delete folder /path/to/folder
```

The app lists the files or folders that would be deleted. Nothing is deleted unless you type `APPLY`.

You can also force the prompt mode:

```bash
python -m file_organizer --interactive
```

## Real Folder Usage

Interactive mode is recommended:

```bash
python -m file_organizer
```

Useful prompts:

```text
organize my Downloads
organize my Downloads and move into the user folder
organize folder /path/to/folder and output /path/to/destination
organize my Desktop and create folders if needed
delete trash in the trash can
```

If you use direct CLI mode, add AI flags explicitly:

```bash
python -m file_organizer ~/Downloads --use-ai --ai-scope all --ai-prefer --ai-custom-folders
```

Then apply only when the plan looks correct:

```bash
python -m file_organizer ~/Downloads --use-ai --ai-scope all --ai-prefer --ai-custom-folders --apply
```

## Memory Rules

You can teach the agent simple extension rules:

```bash
python -m file_organizer --learn-extension .ipynb Code/Notebooks
```

Interactive corrections also teach the agent. For example:

```text
FIX 1 Projects/Python
```

That saves a memory rule for that filename, so future runs can reuse your correction.

## Output Structure

By default, direct CLI mode moves files into an `Organized` folder inside the selected folder.

Interactive mode can also move files directly into another destination. For example, if you ask to move Downloads into the user folder, it creates only the needed category folders directly under the user folder:

```text
/Users/you/Documents/Text/
/Users/you/Research/
/Users/you/Ideas/Text/
```

It does not create every possible category ahead of time.

Typical category structure:

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

The agent never moves or deletes files unless you pass `--apply` in direct CLI mode or type `APPLY` after an interactive preview. It also avoids overwriting by generating names like `file (1).pdf` when a destination already exists.

## AI Authentication Notes

This project does not reuse your Codex or ChatGPT login. The OpenAI API uses API keys for normal server-side authentication, so the key is read from `OPENAI_API_KEY` or `.env`; it is not stored in GitHub.

The AI labeling module sends only file metadata and a short text preview, not the whole folder. It asks the model to return structured JSON with:

- category
- subfolder
- confidence
- summary
- reason

Interactive mode prefers valid AI labels. If the AI provider is unavailable, errors, returns invalid JSON, or suggests an unsafe folder name, the agent falls back to local rules and explains that in the plan.
