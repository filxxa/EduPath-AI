import pytest

from backend.documents.classification import classify_document


@pytest.mark.parametrize(
    ("filename", "category"),
    [
        ("matric_result.txt", "matric_certificate"),
        ("ssc_certificate.txt", "matric_certificate"),
        ("hssc_transcript.txt", "intermediate_transcript"),
        ("fsc_marks.txt", "intermediate_transcript"),
        ("ics_result.txt", "intermediate_transcript"),
        ("a-level_results.txt", "intermediate_transcript"),
        ("nat_result.txt", "entry_test_score"),
        ("b-form.txt", "cnic_bform"),
    ],
)
def test_classifies_representative_filenames(filename: str, category: str) -> None:
    result = classify_document(filename)

    assert result["canonical_category"] == category
    assert result["method"] == "filename"


def test_classifies_from_content_when_filename_is_uninformative() -> None:
    result = classify_document(
        "upload.txt", "Higher Secondary School Certificate for FSc Pre-Engineering"
    )

    assert result["canonical_category"] == "intermediate_transcript"
    assert result["method"] == "content"


def test_filename_classification_takes_precedence_over_content() -> None:
    result = classify_document("matric_result.txt", "NAT entry test score")

    assert result["canonical_category"] == "matric_certificate"
    assert result["method"] == "filename"


def test_unknown_document_uses_supporting_document_fallback() -> None:
    result = classify_document("notes.txt", "general notes")

    assert result == {
        "canonical_category": None,
        "document_type": "Supporting Document",
        "method": "unknown",
    }
