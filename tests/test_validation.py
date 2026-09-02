from backend.documents.validation import MAX_FILE_SIZE_BYTES, validate_upload


def test_accepts_valid_text_file() -> None:
    result = validate_upload("transcript.txt", b"Name: Ali Hassan")

    assert result.valid
    assert result.errors == []


def test_rejects_empty_file() -> None:
    result = validate_upload("transcript.txt", b"")

    assert not result.valid
    assert result.errors == ["File is empty."]


def test_rejects_unsupported_extension() -> None:
    result = validate_upload("transcript.docx", b"document")

    assert not result.valid
    assert "Unsupported file type '.docx'" in result.errors[0]


def test_rejects_oversized_file() -> None:
    result = validate_upload("transcript.txt", b"x" * (MAX_FILE_SIZE_BYTES + 1))

    assert not result.valid
    assert "File is too large" in result.errors[0]


def test_rejects_corrupted_text_file() -> None:
    result = validate_upload("transcript.txt", b"text\x00content")

    assert not result.valid
    assert result.errors == ["Text file appears corrupted or binary."]


def test_accepts_pdf_as_manual_entry_placeholder() -> None:
    result = validate_upload("transcript.pdf", b"%PDF")

    assert result.valid
    assert "accepted but not parsed" in result.warnings[0]
