from pathlib import Path
import json

from file_organizer.ai_labeler import JSON_FORMAT_INSTRUCTION, _build_prompt, _parse_response_text
from file_organizer.models import Classification, FileSignal


def fallback() -> Classification:
    return Classification(
        category="Review",
        subfolder=None,
        confidence=0.25,
        reason="fallback",
    )


def test_parse_openai_compatible_json_content() -> None:
    result = _parse_response_text(
        '{"category":"Code","subfolder":"Python","confidence":0.95,'
        '"summary":"Python script.","reason":"File extension indicates Python code."}',
        fallback(),
        source="ai-openai-compatible",
        allow_custom_folders=False,
    )
    assert result.source == "ai-openai-compatible"
    assert result.category == "Code"
    assert result.subfolder == "Python"
    assert result.confidence == 0.95


def test_parse_quoted_json_content() -> None:
    quoted_json = json.dumps(
        '{"category":"Meetings","subfolder":"Text","confidence":0.9,'
        '"summary":"Team notes.","reason":"Content contains meeting action items."}'
    )
    result = _parse_response_text(
        quoted_json,
        fallback(),
        source="ai-openai-compatible",
        allow_custom_folders=False,
    )
    assert result.category == "Meetings"
    assert result.subfolder == "Text"
    assert result.confidence == 0.9


def test_parse_content_parts() -> None:
    result = _parse_response_text(
        [
            {
                "text": '{"category":"Data","subfolder":"CSV","confidence":0.87,'
                '"summary":"Export table.","reason":"CSV content has structured rows."}'
            }
        ],
        fallback(),
        source="ai-openai",
        allow_custom_folders=False,
    )
    assert result.category == "Data"
    assert result.subfolder == "CSV"
    assert result.confidence == 0.87


def test_json_instruction_contains_complete_example() -> None:
    assert '"confidence":0.90' in JSON_FORMAT_INSTRUCTION
    assert "Return exactly one complete JSON object" in JSON_FORMAT_INSTRUCTION
    assert "Use null for subfolder" in JSON_FORMAT_INSTRUCTION


def test_prompt_reinforces_complete_json_example() -> None:
    signal = FileSignal(
        path=Path("/tmp/literature.docx"),
        relative_path=Path("literature.docx"),
        name="literature.docx",
        extension=".docx",
        size_bytes=100,
        modified_at="2026-01-01T00:00:00",
        created_at="2026-01-01T00:00:00",
        mime_type=None,
    )
    prompt = _build_prompt(signal, fallback(), allow_custom_folders=True)

    assert '"category":"Research"' in prompt
    assert '"confidence":0.90' in prompt
    assert "Do not stop after a key like \"confidence\"" in prompt
