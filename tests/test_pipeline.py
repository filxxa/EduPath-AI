import pytest

import io

from backend.documents import ocr
from backend.documents.ocr import OcrResult
from backend.documents.pipeline import (
    process_upload,
    process_uploads,
    process_uploads_and_propose_profile,
    propose_profile,
)

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - exercised when runtime deps are absent.
    fitz = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised when runtime deps are absent.
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]


INTERMEDIATE_CONTENT = (
    b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4\nNAT Score: 89"
)


def test_process_upload_runs_document_pipeline() -> None:
    document = process_upload("hssc_transcript.txt", INTERMEDIATE_CONTENT)

    assert document.validation.valid
    assert document.canonical_category == "intermediate_transcript"
    assert document.extraction_method == "text"
    assert document.field_value("name") == "Ali Hassan"
    assert document.field_value("qualification") == "FSc Pre-Engineering"
    assert document.field_value("aggregate") == 88.4


def test_invalid_upload_short_circuits_pipeline() -> None:
    document = process_upload("transcript.docx", b"content")

    assert not document.validation.valid
    assert document.document_type == "Unsupported / Invalid File"
    assert document.extraction_method == "none"
    assert document.fields == []


def test_process_uploads_handles_multiple_files() -> None:
    documents = process_uploads(
        [
            ("hssc_transcript.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", b"Name: Ali Hassan\nCNIC 12345"),
        ]
    )

    assert [document.canonical_category for document in documents] == [
        "intermediate_transcript",
        "cnic_bform",
    ]


def test_process_upload_propagates_extraction_metadata_and_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.documents.pipeline.extract_text",
        lambda filename, content: {
            "raw_text": "Name: Ali Hassan",
            "extraction_method": "image_ocr",
            "ocr_note": "Verify OCR output.",
            "is_scanned_pdf": False,
            "ocr_confidence": 85.0,
            "page_count": None,
            "pages_processed": None,
            "errors": ["OCR could not read all content."],
            "warnings": ["Verify OCR output."],
        },
    )

    document = process_upload("scan.png", b"\x89PNG\r\n\x1a\nimage")

    assert not document.validation.valid
    assert document.validation.errors == ["OCR could not read all content."]
    assert document.validation.warnings == ["Verify OCR output."]
    assert document.ocr_confidence == 85.0
    assert len(document.fields) == 1
    assert document.fields[0].field == "name"
    assert document.fields[0].value == "Ali Hassan"


def test_processes_uploads_and_builds_profile_proposal() -> None:
    documents, proposal = process_uploads_and_propose_profile(
        [
            ("hssc_transcript.txt", INTERMEDIATE_CONTENT),
            (
                "matric_result.txt",
                b"Name: Ali Hassan\nBISE Lahore\nAggregate: 92.0",
            ),
        ]
    )

    assert len(documents) == 2
    assert proposal.profile["name"] == "Ali Hassan"
    assert proposal.profile["aggregate"] == 88.4


def test_only_valid_classified_uploads_count_as_profile_documents() -> None:
    documents, proposal = process_uploads_and_propose_profile(
        [
            ("cnic.txt", b"attachment"),
            ("supporting.txt", b"attachment"),
            ("invalid.docx", b"attachment"),
        ]
    )

    assert documents[0].validation.valid
    assert documents[0].canonical_category == "cnic_bform"
    assert documents[0].fields == []
    assert documents[1].validation.valid
    assert documents[1].canonical_category is None
    assert not documents[2].validation.valid
    assert proposal.profile["documents"] == ["CNIC / B-Form"]


def test_document_serialization_preserves_flattened_split_fields() -> None:
    document = process_upload("hssc_transcript.txt", INTERMEDIATE_CONTENT)

    serialized = document.to_dict()
    round_tripped = type(document).from_dict(serialized)

    assert serialized["hssc_percentage"] == 88.4
    assert serialized["ssc_percentage"] is None
    assert serialized["hssc_group"] == "Pre-Engineering"
    assert round_tripped.field_value("hssc_percentage") == 88.4
    assert round_tripped.field_value("hssc_group") == "Pre-Engineering"


@pytest.mark.skipif(fitz is None, reason="PyMuPDF is not installed")
def test_scanned_pdf_ocr_extracts_name_and_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scanned marksheet rendered to images and OCR'd must yield structured fields."""
    scanned_text = (
        "Name: Ali Hassan\n"
        "Father Name: Hassan Ahmed\n"
        "Roll Number: 123456\n"
        "Qualification: FSc Pre-Engineering\n"
        "Board: BISE Lahore\n"
        "Aggregate: 88.4%"
    )
    monkeypatch.setattr(
        "backend.documents.pdf.extract_image_ocr",
        lambda content: OcrResult(raw_text=scanned_text, confidence=91.0, word_count=12),
    )

    document = fitz.open()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()

    result = process_upload("hssc_scan.pdf", pdf_bytes)

    assert result.validation.valid
    assert result.extraction_method == "pdf_ocr"
    assert result.is_scanned_pdf is True
    assert result.canonical_category == "intermediate_transcript"
    assert result.field_value("name") == "Ali Hassan"
    assert result.field_value("qualification") == "FSc Pre-Engineering"
    assert result.field_value("aggregate") == 88.4
    assert result.field_value("hssc_percentage") == 88.4
    assert result.ocr_confidence == 91.0
    assert "OCR" in (result.ocr_note or "")


@pytest.mark.skipif(fitz is None, reason="PyMuPDF is not installed")
def test_scanned_pdf_ocr_unavailable_returns_controlled_diagnostic(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Tesseract is unavailable the pipeline must report a clear diagnostic, not crash."""
    monkeypatch.setattr(
        "backend.documents.pdf.extract_image_ocr",
        lambda content: OcrResult(
            status="unavailable",
            message="Tesseract OCR was not found. Install Tesseract or set TESSERACT_CMD.",
        ),
    )

    document = fitz.open()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()

    result = process_upload("hssc_scan.pdf", pdf_bytes)

    assert result.validation.valid
    assert result.extraction_method == "unavailable"
    assert result.is_scanned_pdf is None
    assert result.canonical_category == "intermediate_transcript"
    assert result.fields == []
    assert any("not available" in warning.lower() for warning in result.validation.warnings)
    assert "not available" in (result.ocr_note or "").lower()


@pytest.mark.skipif(fitz is None, reason="PyMuPDF is not installed")
@pytest.mark.skipif(Image is None, reason="PIL is not installed")
@pytest.mark.skipif(not ocr.tesseract_available(), reason="English Tesseract is unavailable")
def test_real_scanned_pdf_pipeline_extracts_pakistani_marksheet() -> None:
    """A genuine image-based marksheet PDF must be OCR'd and parsed end-to-end."""
    assert Image is not None
    assert ImageDraw is not None

    width, height = 1700, 2200
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font = ImageFont.load_default()

    lines = [
        "BOARD OF INTERMEDIATE AND SECONDARY EDUCATION LAHORE",
        "HIGHER SECONDARY SCHOOL CERTIFICATE (ANNUAL EXAMINATION 2024)",
        "",
        "Name of Candidate: AHMAD RAZA KHAN",
        "Father's Name: MUHAMMAD RAZA KHAN",
        "Roll Number: 123456",
        "Institution: GOVT COLLEGE LAHORE",
        "",
        "Group: FSc Pre-Engineering",
        "",
        "Subject                        Marks Obtained    Total Marks",
        "English                            82              100",
        "Urdu                               78              100",
        "Islamic Studies                    48               50",
        "Pakistan Studies                   47               50",
        "Physics                            91              100",
        "Chemistry                          88              100",
        "Mathematics                        95              100",
        "",
        "Total Obtained Marks: 529",
        "Total Marks: 700",
        "Aggregate Percentage: 75.57%",
    ]

    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 62

    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format="PDF", resolution=200.0)

    result = process_upload("hssc_marksheet_scanned.pdf", pdf_bytes.getvalue())

    assert result.validation.valid
    assert result.extraction_method == "pdf_ocr"
    assert result.is_scanned_pdf is True
    assert result.canonical_category == "intermediate_transcript"
    assert result.field_value("name") == "Ahmad Raza Khan"
    assert result.field_value("qualification") == "FSc Pre-Engineering"
    assert result.field_value("board") == "BISE Lahore"
    assert result.field_value("aggregate") == 75.57
    assert result.field_value("hssc_percentage") == 75.57
    assert result.field_value("hssc_group") == "Pre-Engineering"
    assert result.ocr_confidence is not None
    assert result.ocr_confidence > 80.0


def test_pipeline_bytes_are_non_destructive_across_multiple_calls() -> None:
    """The same bytes passed through the pipeline multiple times must yield identical results."""
    content = b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4"

    results = [process_upload("hssc_transcript.txt", content) for _ in range(3)]

    for result in results:
        assert result.field_value("name") == "Ali Hassan"
        assert result.field_value("qualification") == "FSc Pre-Engineering"
        assert result.field_value("board") == "BISE Lahore"
        assert result.field_value("aggregate") == 88.4


def test_bytesio_seek_before_getvalue_preserves_content() -> None:
    """Simulates the Streamlit upload pattern: seek(0) before getvalue() ensures
    the full content is read even if the stream position was moved."""
    content = b"Name: Sara Khan\nFSc Pre-Medical\nBISE Karachi\nAggregate: 82.5"
    stream = io.BytesIO(content)

    stream.read(10)
    stream.seek(0)
    read_bytes = stream.getvalue()
    stream.seek(0)

    result = process_upload("hssc_transcript.txt", read_bytes)

    assert result.field_value("name") == "Sara Khan"
    assert result.field_value("aggregate") == 82.5


@pytest.mark.skipif(fitz is None, reason="PyMuPDF is not installed")
@pytest.mark.skipif(Image is None, reason="PIL is not installed")
@pytest.mark.skipif(not ocr.tesseract_available(), reason="English Tesseract is unavailable")
def test_end_to_end_multi_document_pipeline_with_merged_profile() -> None:
    """Full pipeline: scanned PDF + text documents → OCR → extraction → classification → merged profile."""
    assert Image is not None
    assert ImageDraw is not None

    width, height = 1700, 2200
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font = ImageFont.load_default()

    lines = [
        "BOARD OF INTERMEDIATE AND SECONDARY EDUCATION LAHORE",
        "HIGHER SECONDARY SCHOOL CERTIFICATE (ANNUAL EXAMINATION 2024)",
        "",
        "Name of Candidate: FATIMA ABBAS",
        "Father's Name: GHULAM ABBAS",
        "Roll Number: 789012",
        "Institution: PUNJAB COLLEGE LAHORE",
        "",
        "Group: FSc Pre-Engineering",
        "",
        "Subject                        Marks Obtained    Total Marks",
        "English                            85              100",
        "Urdu                               80              100",
        "Islamic Studies                    45               50",
        "Pakistan Studies                   46               50",
        "Physics                            92              100",
        "Chemistry                          90              100",
        "Mathematics                        97              100",
        "",
        "Total Obtained Marks: 535",
        "Total Marks: 700",
        "Aggregate Percentage: 76.43%",
    ]

    y = 80
    for line in lines:
        draw.text((80, y), line, fill="black", font=font)
        y += 62

    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format="PDF", resolution=200.0)

    matric_text = (
        "BOARD OF INTERMEDIATE AND SECONDARY EDUCATION KARACHI\n"
        "SECONDARY SCHOOL CERTIFICATE (ANNUAL EXAMINATION 2022)\n"
        "\n"
        "Name of Candidate: FATIMA ABBAS\n"
        "Father's Name: GHULAM ABBAS\n"
        "Roll Number: 456789\n"
        "\n"
        "Total Obtained Marks: 980\n"
        "Total Marks: 1100\n"
        "Aggregate Percentage: 89.09%\n"
    )

    nat_text = (
        "National Aptitude Test (NAT) Score Card\n"
        "Candidate Name: Fatima Abbas\n"
        "Test Date: 2024-06-15\n"
        "Score: 92\n"
    )

    uploads = [
        ("hssc_marksheet_scanned.pdf", pdf_bytes.getvalue()),
        ("matric_result.txt", matric_text.encode("utf-8")),
        ("nat_score.txt", nat_text.encode("utf-8")),
    ]

    docs = process_uploads(uploads)

    assert len(docs) == 3

    hssc_doc = next(d for d in docs if d.filename == "hssc_marksheet_scanned.pdf")
    matric_doc = next(d for d in docs if d.filename == "matric_result.txt")
    nat_doc = next(d for d in docs if d.filename == "nat_score.txt")

    assert hssc_doc.canonical_category == "intermediate_transcript"
    assert hssc_doc.extraction_method == "pdf_ocr"
    assert hssc_doc.is_scanned_pdf is True
    assert hssc_doc.validation.valid
    assert hssc_doc.field_value("name") is not None
    assert hssc_doc.field_value("aggregate") is not None
    assert hssc_doc.ocr_confidence is not None
    assert hssc_doc.ocr_confidence > 50.0

    assert matric_doc.canonical_category == "matric_certificate"
    assert matric_doc.extraction_method == "text"
    assert matric_doc.field_value("name") == "Fatima Abbas"
    assert matric_doc.field_value("aggregate") == 89.09

    assert nat_doc.canonical_category == "entry_test_score"
    assert nat_doc.extraction_method == "text"
    test_score = nat_doc.field_value("test_score")
    assert isinstance(test_score, dict)
    assert test_score["test"] == "NAT"
    assert test_score["score"] == "92"

    proposal = propose_profile(docs)

    profile = proposal.profile
    assert profile.get("name") is not None
    assert profile.get("hssc_percentage") is not None
    assert profile.get("ssc_percentage") is not None
    test_scores = profile.get("test_scores")
    assert test_scores is not None
    assert "NAT" in test_scores
    assert len(proposal.conflicts) > 0
    conflict_fields = {c.field for c in proposal.conflicts}
    assert "board" in conflict_fields
    assert "aggregate" in conflict_fields
