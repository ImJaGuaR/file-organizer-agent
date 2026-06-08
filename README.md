# File Organizer Agent

An AI-agent-driven folder organizer. The model is the primary planner: it reads the user's natural-language request, inspects safe metadata and short previews, reasons about the folder as a whole, proposes a semantic folder structure, explains each action, and revises the plan from user feedback.

The deterministic Python code does safety work only: scanning, preview limits, schema validation, path sanitization, duplicate handling, approval enforcement, filesystem moves, reports, and tests. Default mode has no local rule fallback and no extension-to-folder classifier.

## Safety Model

- The app previews every plan before changing files.
- Move/delete actions require approval unless `--apply` is explicitly passed.
- Deletes are not permanent. Approved delete actions are moved to `_To_Delete_Review`.
- Hidden files, symlinks, protected folders, dependency folders, and secret-like files are skipped or treated as high risk by default.
- File previews are short, size-limited, and disabled for likely secrets such as `.env`, `id_rsa`, token, password, key, and credentials files.
- AI destinations are validated so they cannot escape the allowed destination root or use path traversal.
- Duplicate destination filenames are renamed safely, for example `file (1).txt`.

## Install

Python 3.10+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and configure one provider.

## Provider Setup

OpenAI:

```text
AI_PROVIDER=openai
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-5.4-mini
```

OpenAI-compatible API:

```text
AI_PROVIDER=openai-compatible
OPENAI_COMPATIBLE_API_KEY=your_provider_key
OPENAI_COMPATIBLE_BASE_URL=https://api.example.com/v1
OPENAI_COMPATIBLE_MODEL=provider/model
```

Ollama:

```text
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
```

Check configuration:

```bash
python -m file_organizer --auth-status
```

If the selected provider is unavailable, default agent mode fails clearly:

```text
AI provider unavailable, cannot create semantic organization plan.
```

It will not silently organize by local rules.

## Run

Interactive agent mode:

```bash
python -m file_organizer
```

Example request:

```text
organize my Downloads into a clean structure, keep university stuff separate, don't touch apps or installers, and ask me before moving anything
```

Direct target mode:

```bash
python -m file_organizer ~/Downloads
```

Preview a recursive plan:

```bash
python -m file_organizer ~/Downloads --recursive --max-files 300
```

Apply without an interactive approval prompt:

```bash
python -m file_organizer ~/Downloads --apply
```

Use a specific provider/model:

```bash
python -m file_organizer ~/Downloads --provider ollama --model llama3.1
```

## Interactive Commands

After the agent shows a preview, use:

- `APPLY` applies the validated plan. High-risk actions ask for an extra confirmation.
- `CANCEL` leaves files unchanged.
- `WHY <id>` explains an action.
- `EDIT <id> <relative/folder/path>` changes one destination and saves a natural-language preference.
- `SKIP <id>` changes an action to skip.
- `DELETE <id>` marks an item for delete review; it still needs approval.
- `MEMORY` shows active natural-language memory.
- `FORGET MEMORY` deactivates saved memory.
- `HELP` lists commands.

Natural-language revisions also work, for example:

```text
put all screenshots into Korea trip
make fewer folders
actually keep PDFs in the same folder
make it organized by project, not file type
```

The agent asks the model to revise the current structured plan instead of using a command parser as a classifier.

## Memory

Memory is stored as natural-language preferences in:

```text
~/.file_organizer_agent/memory.json
```

Example memory items:

- User prefers university files to be grouped by course name when course is identifiable.
- User wants screenshots from Korea/Japan trips under Travel.
- User does not want installers moved unless explicitly asked.
- User prefers fewer broad folders instead of many file-type folders.

The app does not save brittle extension rules such as `.jpg -> Images`.

## Architecture

```text
file_organizer/
  agent/
    loop.py       interactive agent loop and revision flow
    prompts.py    system and repair prompts
    tools.py      safe tool wrappers
    schemas.py    strict plan, action, file, and memory schemas
    memory.py     natural-language memory store
    planner.py    AI plan generation plus deterministic validation
    executor.py   approved safe execution
  providers/
    base.py
    openai_provider.py
    compatible_provider.py
    ollama_provider.py
  core/
    scanner.py
    preview.py
    safety.py
    reports.py
    paths.py
  cli.py
  __main__.py
```

The model decides folder names and destinations. The code validates and executes.

## Reports

JSON and Markdown reports are written under the destination root's `Reports` folder. Reports include:

- request
- source and destination folders
- provider/model
- files scanned and previewed
- actions proposed and applied
- skipped items and warnings
- user edits
- memory updates
- timestamp

Use `--no-report` to skip report writing.

## Emergency Deterministic Mode

`--deterministic-basic` is available only as a clearly marked emergency mode. It is off by default and is not semantic agent mode. It stages visible files into `Review` without extension classification.

```bash
python -m file_organizer ~/Downloads --deterministic-basic
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

Current tests cover:

- no local rule fallback when AI is unavailable
- one invalid-JSON repair attempt
- path traversal and outside-root blocking
- preview mode safety
- approved apply moves
- duplicate destination renaming
- hidden/risky file handling
- secret preview blocking
- edit/skip interactions
- natural-language memory
- absence of hardcoded extension classification in default source

## Privacy Notes

The provider receives file metadata and short safe previews only, not full file contents. Secret-like filenames are not previewed. For very private folders, use a local provider such as Ollama and review the preview table carefully before applying anything.

