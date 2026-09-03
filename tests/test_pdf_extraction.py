import pytest

fitz = pytest.importorskip("fitz")

from backend.documents import ocr, pdf
from backend.documents.ocr import OcrResult


def text_pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    return content


def blank_pdf_bytes(page_total: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(page_total):
        document.new_page()
    content = document.tobytes()
    document.close()
    return content


def test_extracts_embedded_pdf_text() -> None:
    long_text = (
        "Name: Ali Hassan\n"
        "Father Name: Hassan Ahmed\n"
        "Roll Number: 123456\n"
        "Qualification: FSc Pre-Engineering\n"
        "Board: BISE Lahore\n"
        "Aggregate: 88.4%\n"
        "This is a genuine text-based marksheet with enough content that the PDF text layer "
        "should be used directly without invoking OCR fallback."
    )
    result = pdf.extract_pdf(text_pdf_bytes(long_text))

    assert result.extraction_method == "pdf_text"
    assert result.is_scanned_pdf is False
    assert "Name: Ali Hassan" in result.raw_text
    assert result.page_count == 1
    assert result.pages_processed == 1


def test_extracts_scanned_pdf_via_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pdf,
        "extract_image_ocr",
        lambda content: OcrResult(
            raw_text="Name: Ali Hassan\nAggregate: 88.4",
            confidence=88.0,
            word_count=4,
        ),
    )

    result = pdf.extract_pdf(blank_pdf_bytes())

    assert result.extraction_method == "pdf_ocr"
    assert result.is_scanned_pdf is True
    assert result.raw_text == "Name: Ali Hassan\nAggregate: 88.4"
    assert result.ocr_confidence == 88.0


def test_extracts_hybrid_pdf_in_page_order(monkeypatch: pytest.MonkeyPatch) -> None:
    long_text = (
        "Name: Ali Hassan\n"
        "Father Name: Hassan Ahmed\n"
        "Roll Number: 123456\n"
        "Qualification: FSc Pre-Engineering\n"
        "Board: BISE Lahore\n"
        "Aggregate: 88.4%\n"
        "This genuine text-based marksheet page has enough embedded content to stay "
        "above the text-layer threshold, while the next page is blank and must be OCR processed."
    )
    document = fitz.open()
    first = document.new_page()
    first.insert_text((72, 72), long_text)
    document.new_page()
    content = document.tobytes()
    document.close()
    monkeypatch.setattr(
        pdf,
        "extract_image_ocr",
        lambda content: OcrResult(raw_text="NAT Score: 89", confidence=80.0, word_count=3),
    )

    result = pdf.extract_pdf(content)

    assert result.extraction_method == "pdf_hybrid"
    assert result.is_scanned_pdf is True
    assert result.raw_text.index("Name: Ali Hassan") < result.raw_text.index("NAT Score: 89")


def test_reports_corrupt_pdf() -> None:
    result = pdf.extract_pdf(b"%PDF-1.7\nnot valid")

    assert result.extraction_method == "error"
    assert result.errors == ["This PDF appears corrupt or unreadable."]


def test_reports_password_protected_pdf() -> None:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Protected transcript")
    content = document.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        user_pw="user",
    )
    document.close()

    result = pdf.extract_pdf(content)

    assert result.extraction_method == "error"
    assert "password-protected" in result.errors[0]


def test_enforces_pdf_page_and_scanned_ocr_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_ocr(content: bytes) -> OcrResult:
        nonlocal calls
        calls += 1
        return OcrResult(raw_text=f"Page {calls} text", confidence=75.0, word_count=2)

    monkeypatch.setattr(pdf, "extract_image_ocr", fake_ocr)

    result = pdf.extract_pdf(blank_pdf_bytes(page_total=11))

    assert result.page_count == 11
    assert result.pages_processed == pdf.MAX_PDF_PAGES
    assert calls == pdf.MAX_OCR_PAGES
    assert any("first 10 PDF pages" in warning for warning in result.warnings)
    assert any("first 5 scanned PDF pages" in warning for warning in result.warnings)


def test_reports_unavailable_ocr_for_scanned_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pdf,
        "extract_image_ocr",
        lambda content: OcrResult(status="unavailable", message="OCR unavailable"),
    )

    result = pdf.extract_pdf(blank_pdf_bytes())

    assert result.extraction_method == "unavailable"
    assert "not available" in result.warnings[0]


@pytest.mark.skipif(not ocr.tesseract_available(), reason="English Tesseract is unavailable")
def test_runs_tesseract_on_generated_scanned_pdf() -> None:
    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new("RGB", (900, 250), color="white")
    ImageDraw.Draw(image).text((30, 80), "Name: Ali Hassan", fill="black", font_size=48)
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    document = fitz.open()
    page = document.new_page(width=900, height=250)
    page.insert_image(page.rect, stream=image_bytes.getvalue())
    content = document.tobytes()
    document.close()

    result = pdf.extract_pdf(content)

    assert result.extraction_method == "pdf_ocr"
    assert "Ali" in result.raw_text
