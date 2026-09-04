import pytest

from backend.documents.extraction import extract_text
from backend.documents.fields import (
    _number_from_words,
    extract_aggregate,
    extract_board,
    extract_father_name,
    extract_fields,
    extract_name,
    extract_obtained_marks,
    extract_qualification,
    extract_test_score,
    extract_total_marks,
)
from backend.documents.ocr import OcrResult
from backend.documents.pdf import PdfExtraction


@pytest.mark.parametrize("filename", ["profile.txt", "profile.md", "profile.csv"])
def test_extracts_supported_text_files(filename: str) -> None:
    result = extract_text(filename, b"Name: Ali Hassan")

    assert result["raw_text"] == "Name: Ali Hassan"
    assert result["extraction_method"] == "text"
    assert result["ocr_note"] is None


def test_wraps_successful_image_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.documents.extraction.extract_image_ocr",
        lambda content: OcrResult(raw_text="Name: Ali Hassan", confidence=91.5, word_count=3),
    )

    result = extract_text("scan.png", b"image")

    assert result["raw_text"] == "Name: Ali Hassan"
    assert result["extraction_method"] == "image_ocr"
    assert result["ocr_confidence"] == 91.5
    assert "92%" in result["ocr_note"]


def test_wraps_unavailable_image_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.documents.extraction.extract_image_ocr",
        lambda content: OcrResult(status="unavailable", message="OCR is not available on this server."),
    )

    result = extract_text("scan.jpg", b"image")

    assert result["extraction_method"] == "unavailable"
    assert result["errors"] == []
    assert "not available" in result["warnings"][0]


def test_wraps_pdf_text_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.documents.extraction.extract_pdf",
        lambda content: PdfExtraction(
            raw_text="Name: Ali Hassan",
            extraction_method="pdf_text",
            is_scanned_pdf=False,
            page_count=1,
            pages_processed=1,
        ),
    )

    result = extract_text("transcript.pdf", b"%PDF-1.7")

    assert result["raw_text"] == "Name: Ali Hassan"
    assert result["extraction_method"] == "pdf_text"
    assert result["is_scanned_pdf"] is False
    assert result["page_count"] == 1


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

    assert result == {"test": "NAT", "score": "89", "total_score": None, "test_date": None, "roll_number": None}


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
        "hssc_percentage": 88.4,
        "hssc_group": "Pre-Engineering",
        "test_score": {"test": "NAT", "score": "89", "total_score": None, "test_date": None, "roll_number": None},
    }
    assert all(field.confidence is None for field in fields)


def test_extracts_inline_name_of_candidate_and_normalizes_ocr_caps() -> None:
    assert extract_name("Name of Candidate: ALI HASSAN") == "Ali Hassan"


def test_extracts_candidate_name_from_next_nonempty_line() -> None:
    text = "Name of Candidate\n\nAli Hassan\nRoll Number: 12345"

    assert extract_name(text) == "Ali Hassan"


@pytest.mark.parametrize(
    "text",
    [
        "Name of Candidate\nFather Name Ahmed Khan",
        "Name: Roll Number 12345",
        "Name: Board of Intermediate Education",
    ],
)
def test_rejects_name_metadata_as_student_name(text: str) -> None:
    assert extract_name(text) is None


def test_calculates_percentage_from_valid_obtained_total_ratio() -> None:
    assert extract_aggregate("Marks Obtained: 850\nTotal Marks: 1100") == 77.27


def test_prefers_labeled_aggregate_over_obtained_total_ratio() -> None:
    text = "Aggregate: 82.5%\nMarks Obtained: 950 / 1100"

    assert extract_aggregate(text) == 82.5


def test_rejects_bare_result_year_as_aggregate() -> None:
    assert extract_aggregate("Result: 2023\nRoll Number: 12345") is None


def test_extracts_all_caps_pakistani_marksheet() -> None:
    """OCR frequently returns Pakistani marksheets in all capitals."""
    text = (
        "BOARD OF INTERMEDIATE AND SECONDARY EDUCATION LAHORE\n"
        "NAME OF CANDIDATE: AHMAD RAZA KHAN\n"
        "GROUP: FSC PRE-ENGINEERING\n"
        "TOTAL OBTAINED MARKS: 529\n"
        "TOTAL MARKS: 700\n"
        "AGGREGATE PERCENTAGE: 75.57%"
    )

    fields = extract_fields("hssc_scan.pdf", text, "intermediate_transcript")
    values = {field.field: field.value for field in fields}

    assert values["name"] == "Ahmad Raza Khan"
    assert values["qualification"] == "FSc Pre-Engineering"
    assert values["board"] == "BISE Lahore"
    assert values["aggregate"] == 75.57
    assert values["hssc_percentage"] == 75.57
    assert values["hssc_group"] == "Pre-Engineering"


def test_extracts_mixed_case_with_ocr_whitespace_and_line_breaks() -> None:
    """OCR whitespace and line breaks must not break field extraction."""
    text = (
        "Board   of   Intermediate   and   Secondary   Education   Lahore\n\n"
        "Name of Candidate:\n  ali  hassan  khan  \n\n"
        "Qualification:  fsc   pre-engineering\n"
        "Marks  Obtained  :   850\n"
        "Total   Marks :   1100"
    )

    fields = extract_fields("hssc_scan.pdf", text, "intermediate_transcript")
    values = {field.field: field.value for field in fields}

    assert values["name"] == "Ali Hassan Khan"
    assert values["qualification"] == "FSc Pre-Engineering"
    assert values["board"] == "BISE Lahore"
    assert values["aggregate"] == 77.27
    assert values["hssc_percentage"] == 77.27


def test_extracts_obtained_total_variants() -> None:
    assert extract_aggregate("Obtained Marks 900 / Total Marks 1100") == 81.82
    assert extract_aggregate("Marks Obtained: 529 out of 700") == 75.57
    assert extract_aggregate("OBTAINED 850 TOTAL 1100") == 77.27


_BISE_MIRPURKHAS_OCR = (
    "Board Of Intermediate & Secondary Hducat Mirpurkhas Sindh\n"
    "NAME: MUHAMMAD ADEEL SARFRAZ\n"
    "FATHER'S NAME: SARFRAZ AHMED\n"
    "INSTITUTE: S.A.L GOVT:COLLEGE MIRPURKHAS\n"
    "TOTAL 1100 761\n"
    "OBTAINED MARKS (IN WORDS); SEVEN HUNDRED AND SIXTY ONE."
)


def test_extracts_bise_mirpurkhas_ocr_with_typo_tolerance() -> None:
    """Real OCR from BISE Mirpurkhas: typo in 'Education', TOTAL format, number-in-words."""
    fields = extract_fields("mirpurkhas.pdf", _BISE_MIRPURKHAS_OCR, "intermediate_transcript")
    values = {f.field: f.value for f in fields}

    assert values["name"] == "Muhammad Adeel Sarfraz"
    assert values["father_name"] == "Sarfraz Ahmed"
    assert values["board"] == "BISE Mirpurkhas"
    assert values["aggregate"] == 69.18
    assert values["hssc_percentage"] == 69.18


def test_name_tolerates_trailing_symbols_and_semicolons() -> None:
    assert extract_name("NAME: ALI HASSAN ;") == "Ali Hassan"
    assert extract_name("NAME: JOHN DOE-SMITH |") == "John Doe-Smith"


def test_board_tolerates_education_ocr_typos() -> None:
    assert extract_board("Board Of Intermediate & Secondary Educat Lahore") == "BISE Lahore"
    assert extract_board("Board Of Secondary Hducat Karachi") == "BISE Karachi"
    assert extract_board("Board Of Intermediate & Secondary Educ Islamabad") == "FBISE Islamabad"


def test_total_space_separated_pattern() -> None:
    assert extract_aggregate("TOTAL 1100 761") == 69.18
    assert extract_aggregate("TOTAL MARKS 1100 850") == 77.27


def test_number_from_words_conversion() -> None:
    assert _number_from_words("SEVEN HUNDRED AND SIXTY ONE") == 761
    assert _number_from_words("nine hundred") == 900
    assert _number_from_words("one thousand one hundred") == 1100
    assert _number_from_words("not a number") is None


def test_kv_fallback_fills_missing_name() -> None:
    """When primary name extraction fails, KV fallback should pick up 'Name: ...' patterns."""
    text = (
        "Roll No: 12345\n"
        "Name: Bilal Ahmed\n"
        "Marks Obtained: 850\n"
        "Total Marks: 1100"
    )
    fields = extract_fields("scan.pdf", text, "intermediate_transcript")
    values = {f.field: f.value for f in fields}

    assert values["name"] == "Bilal Ahmed"


def test_kv_fallback_fills_missing_board_and_qualification() -> None:
    """KV fallback should fill board and qualification when primary extraction misses them."""
    text = (
        "Name: Sara Khan\n"
        "Qualification: FSc Pre-Medical\n"
        "Board: BISE Karachi\n"
        "Aggregate: 82.5"
    )
    # Use a filename that won't trigger content-based classification hints
    fields = extract_fields("random.txt", text, None)
    values = {f.field: f.value for f in fields}

    assert values["board"] == "BISE Karachi"
    assert values["qualification"] == "FSc Pre-Medical"


def test_kv_fallback_does_not_override_primary_extraction() -> None:
    """Primary regex extraction should take precedence over KV fallback."""
    text = (
        "Name of Candidate: ALI HASSAN\n"
        "Name: WRONG NAME\n"
        "FSc Pre-Engineering\n"
        "BISE Lahore\n"
        "Aggregate: 90.0"
    )
    fields = extract_fields("hssc.txt", text, "intermediate_transcript")
    values = {f.field: f.value for f in fields}

    assert values["name"] == "Ali Hassan"


def test_kv_fallback_marks_extraction_method() -> None:
    """Fields filled by the KV fallback should have extraction_method='kv_fallback'."""
    text = "Name: Hamza Sheikh\nGuardian: Ahmed Khan\nBoard: BISE Multan"
    fields = extract_fields("doc.txt", text, None)
    kv_fields = [f for f in fields if f.extraction_method == "kv_fallback"]

    assert len(kv_fields) >= 1
    kv_field_names = {f.field for f in kv_fields}
    assert "father_name" in kv_field_names


def test_debug_logging_emits_extraction_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """extract_fields should log a debug summary with file name, text length, and fields."""
    import logging

    text = "Name: Test User\nFSc\nBISE Lahore\nAggregate: 80.0"
    with caplog.at_level(logging.DEBUG, logger="backend.documents.fields"):
        extract_fields("test.pdf", text, "intermediate_transcript")

    assert any("test.pdf" in record.message for record in caplog.records)
    assert any("text_len=" in record.message for record in caplog.records)


def test_extract_obtained_marks_from_labeled_line() -> None:
    text = "TOTAL OBTAINED MARKS: 535\nTOTAL MARKS: 700"
    assert extract_obtained_marks(text) == 535


def test_extract_obtained_marks_various_labels() -> None:
    assert extract_obtained_marks("Marks Obtained: 450") == 450
    assert extract_obtained_marks("TOTAL OBTAINED: 620") == 620


def test_extract_total_marks_from_labeled_line() -> None:
    text = "TOTAL OBTAINED MARKS: 535\nTOTAL MARKS: 700"
    assert extract_total_marks(text) == 700


def test_extract_total_marks_does_not_match_obtained_line() -> None:
    text = "TOTAL OBTAINED MARKS: 535"
    assert extract_total_marks(text) is None


def test_extract_fields_includes_marks() -> None:
    text = (
        "BOARD OF INTERMEDIATE EDUCATION LAHORE\n"
        "NAME: ALI HASSAN\n"
        "FSc PRE-ENGINEERING\n"
        "TOTAL OBTAINED MARKS: 535\n"
        "TOTAL MARKS: 700\n"
        "AGGREGATE: 76.43%"
    )
    fields = extract_fields("hssc.pdf", text, "intermediate_transcript")
    field_map = {f.field: f.value for f in fields}

    assert field_map["obtained_marks"] == 535
    assert field_map["total_marks"] == 700
