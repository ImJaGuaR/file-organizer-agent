import json

from file_organizer.ai_labeler import _parse_response_text
from file_organizer.models import Classification


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
