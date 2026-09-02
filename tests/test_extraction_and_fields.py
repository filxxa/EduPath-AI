import pytest

from backend.documents.extraction import extract_text
from backend.documents.fields import (
    extract_aggregate,
    extract_board,
    extract_fields,
    extract_name,
    extract_qualification,
    extract_test_score,
)


@pytest.mark.parametrize("filename", ["profile.txt", "profile.md", "profile.csv"])
def test_extracts_supported_text_files(filename: str) -> None:
    result = extract_text(filename, b"Name: Ali Hassan")

    assert result["raw_text"] == "Name: Ali Hassan"
    assert result["extraction_method"] == "text"
    assert result["ocr_note"] is None


def test_returns_pdf_placeholder() -> None:
    result = extract_text("transcript.pdf", b"%PDF")

    assert result["raw_text"] == ""
    assert result["extraction_method"] == "placeholder"
    assert "PDF parsing is not enabled" in result["ocr_note"]
    assert result["is_scanned_pdf"] is None


@pytest.mark.parametrize("filename", ["scan.png", "scan.jpg"])
def test_returns_image_placeholder(filename: str) -> None:
    result = extract_text(filename, b"image")

    assert result["raw_text"] == ""
    assert result["extraction_method"] == "placeholder"
    assert "Image OCR is not enabled" in result["ocr_note"]
    assert result["is_scanned_pdf"] is False


def test_extracts_name_without_capturing_the_next_line() -> None:
    name = extract_name("Name: Ali Hassan\nHigher Secondary School Certificate")

    assert name == "Ali Hassan"


def test_extracts_qualification_and_board() -> None:
    text = "FSc Pre-Engineering\nBoard: BISE Lahore"

    assert extract_qualification(text) == "FSc Pre-Engineering"
    assert extract_board(text) == "BISE Lahore"


def test_prefers_aggregate_label_over_unrelated_percentages() -> None:
    text = "Entry test percentage: 73%\nAggregate: 88.4%\nMatric percentage: 91%"

    assert extract_aggregate(text) == 88.4


def test_extracts_test_score() -> None:
    result = extract_test_score("NAT Score: 89")

    assert result == {"test": "NAT", "score": "89"}


def test_does_not_treat_nationality_as_an_entry_test() -> None:
    result = extract_test_score("Certificate of nationality")

    assert result is None


def test_builds_structured_fields() -> None:
    text = "Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4\nNAT Score: 89"

    fields = extract_fields("hssc_transcript.txt", text, "intermediate_transcript")
    values = {field.field: field.value for field in fields}

    assert values == {
        "name": "Ali Hassan",
        "qualification": "FSc Pre-Engineering",
        "board": "BISE Lahore",
        "aggregate": 88.4,
        "test_score": {"test": "NAT", "score": "89"},
    }
