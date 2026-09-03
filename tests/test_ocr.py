import io

import pytest

PIL = pytest.importorskip("PIL")
pytesseract = pytest.importorskip("pytesseract")

from PIL import Image

from backend.documents import ocr


def image_bytes() -> bytes:
    image = Image.new("RGB", (20, 20), color="white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def successful_data() -> dict[str, list[object]]:
    return {
        "text": ["Name:", "Ali", "Hassan", ""],
        "conf": ["90", "80", "70", "-1"],
        "page_num": [1, 1, 1, 1],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }


def test_extracts_text_and_genuine_token_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_availability", lambda: (True, None))
    monkeypatch.setattr(ocr.pytesseract, "image_to_data", lambda *args, **kwargs: successful_data())

    result = ocr.extract_image_ocr(image_bytes())

    assert result.status == "success"
    assert result.raw_text == "Name: Ali Hassan"
    assert result.confidence == 80.0
    assert result.word_count == 3


def test_warns_when_ocr_output_is_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_availability", lambda: (True, None))
    monkeypatch.setattr(
        ocr.pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": [""], "conf": ["-1"]},
    )

    result = ocr.extract_image_ocr(image_bytes())

    assert result.status == "empty"
    assert result.raw_text == ""
    assert "no readable text" in result.message.lower() or "blank" in result.message.lower()


def test_reports_unavailable_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_availability", lambda: (False, "OCR is not available on this server."))

    result = ocr.extract_image_ocr(image_bytes())

    assert result.status == "unavailable"
    assert "not available" in result.message


def test_reports_ocr_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "_availability", lambda: (True, None))

    def timeout(*args: object, **kwargs: object) -> dict[str, list[str]]:
        raise RuntimeError("timeout")

    monkeypatch.setattr(ocr.pytesseract, "image_to_data", timeout)

    result = ocr.extract_image_ocr(image_bytes())

    assert result.status == "error"
    assert "timed out" in result.message


def test_rejects_corrupt_image() -> None:
    result = ocr.extract_image_ocr(b"not an image")

    assert result.status == "error"
    assert "corrupt" in result.message


def test_rejects_image_above_pixel_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr, "MAX_IMAGE_PIXELS", 1)

    result = ocr.extract_image_ocr(image_bytes())

    assert result.status == "error"
    assert "too large" in result.message


@pytest.mark.skipif(not ocr.tesseract_available(), reason="English Tesseract is unavailable")
def test_runs_tesseract_on_generated_image() -> None:
    from PIL import ImageDraw

    image = Image.new("RGB", (900, 250), color="white")
    ImageDraw.Draw(image).text((30, 80), "Name: Ali Hassan", fill="black", font_size=48)
    output = io.BytesIO()
    image.save(output, format="PNG")

    result = ocr.extract_image_ocr(output.getvalue())

    assert result.status == "success"
    assert "Ali" in result.raw_text


def test_prepare_image_applies_exif_rotation() -> None:
    """Phone cameras store rotated images with EXIF orientation tags.

    An image that is 400x200 with EXIF orientation=6 (rotated 90 CW) should
    be transposed to 200x400 by _prepare_image before OCR runs.
    """
    from PIL import ExifTags

    wide_image = Image.new("RGB", (400, 200), color="white")
    exif = wide_image.getexif()
    exif[ExifTags.Base.Orientation] = 6

    jpeg_buffer = io.BytesIO()
    wide_image.save(jpeg_buffer, format="JPEG", exif=exif.tobytes())

    opened = Image.open(io.BytesIO(jpeg_buffer.getvalue()))
    prepared = ocr._prepare_image(opened)

    assert prepared.height > prepared.width
