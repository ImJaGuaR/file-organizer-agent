from pathlib import Path

from file_organizer.classifier import classify_with_rules
from file_organizer.models import FileSignal


def signal(name: str, preview: str = "") -> FileSignal:
    path = Path("/tmp") / name
    return FileSignal(
        path=path,
        relative_path=Path(name),
        name=name,
        extension=path.suffix.lower(),
        size_bytes=123,
        modified_at="2026-01-01T00:00:00",
        created_at="2026-01-01T00:00:00",
        mime_type=None,
        preview=preview,
    )


def test_pdf_classifies_as_documents_pdf() -> None:
    result = classify_with_rules(signal("invoice.pdf"))
    assert result.category == "Documents"
    assert result.subfolder == "PDFs"


def test_research_keywords_override_document_type() -> None:
    result = classify_with_rules(signal("paper.pdf", "abstract methodology references"))
    assert result.category == "Research"


def test_screenshot_image_gets_screenshot_subfolder() -> None:
    result = classify_with_rules(signal("screenshot_123.png"))
    assert result.category == "Images"
    assert result.subfolder == "Screenshots"


def test_unknown_goes_to_review() -> None:
    result = classify_with_rules(signal("mystery.blob"))
    assert result.category == "Review"


def test_voice_memo_project_idea_uses_purpose_before_type() -> None:
    result = classify_with_rules(signal("voice_memo_project_idea.m4a"))
    assert result.category == "Ideas"
    assert result.subfolder == "Audio"


def test_invoice_uses_finance_before_pdf_type() -> None:
    result = classify_with_rules(signal("invoice_april_2026.pdf"))
    assert result.category == "Finance"
    assert result.subfolder == "PDFs"


def test_backup_uses_backup_before_research_project_keyword() -> None:
    result = classify_with_rules(signal("old_project_backup.tar.gz"))
    assert result.category == "Backups"
    assert result.subfolder == "Archives"
