"""Tests for centralized document-status helpers."""
from __future__ import annotations

from backend.document_status import (
    document_exists_vs_extracted,
    get_document_records,
    get_document_status,
    get_uploaded_categories,
    has_document,
)


def _profile_with_records(records):
    return {"document_records": records, "documents": [], "test_scores": {}}


def _legacy_profile(docs):
    return {"document_records": [], "documents": docs, "test_scores": {}}


class TestGetDocumentRecords:
    def test_empty_when_missing(self):
        assert get_document_records({}) == []

    def test_empty_when_none(self):
        assert get_document_records({"document_records": None}) == []

    def test_returns_copy(self):
        records = [{"filename": "a.pdf", "category": "cnic_bform"}]
        profile = {"document_records": records}
        result = get_document_records(profile)
        result.append({"filename": "b.pdf"})
        assert len(get_document_records(profile)) == 1


class TestHasDocument:
    def test_true_when_record_exists(self):
        profile = _profile_with_records([
            {"filename": "cnic.pdf", "category": "cnic_bform", "extraction_status": "extracted"},
        ])
        assert has_document(profile, "cnic_bform") is True

    def test_false_when_category_missing(self):
        profile = _profile_with_records([
            {"filename": "cnic.pdf", "category": "cnic_bform", "extraction_status": "extracted"},
        ])
        assert has_document(profile, "domicile") is False

    def test_empty_profile(self):
        assert has_document({}, "cnic_bform") is False

    def test_legacy_fallback_with_known_doc(self):
        profile = _legacy_profile(["FSc Transcript"])
        assert has_document(profile, "intermediate_transcript") is True

    def test_legacy_fallback_unknown_doc(self):
        profile = _legacy_profile(["random_scan.pdf"])
        assert has_document(profile, "intermediate_transcript") is False


class TestGetDocumentStatus:
    def test_not_uploaded(self):
        profile = _profile_with_records([])
        status = get_document_status(profile, "cnic_bform")
        assert status["uploaded"] is False
        assert status["extraction_status"] == "none"
        assert status["filenames"] == []

    def test_uploaded_and_extracted(self):
        profile = _profile_with_records([
            {"filename": "cnic.pdf", "category": "cnic_bform", "extraction_status": "extracted", "fields": {"name": "Ali"}},
        ])
        status = get_document_status(profile, "cnic_bform")
        assert status["uploaded"] is True
        assert status["extraction_status"] == "extracted"
        assert status["filenames"] == ["cnic.pdf"]
        assert status["fields"]["name"] == "Ali"

    def test_multiple_docs_best_status_wins(self):
        profile = _profile_with_records([
            {"filename": "test1.pdf", "category": "entry_test_score", "extraction_status": "failed", "fields": {}},
            {"filename": "test2.pdf", "category": "entry_test_score", "extraction_status": "extracted", "fields": {"score": 90}},
        ])
        status = get_document_status(profile, "entry_test_score")
        assert status["uploaded"] is True
        assert status["extraction_status"] == "extracted"
        assert len(status["filenames"]) == 2

    def test_partial_status(self):
        profile = _profile_with_records([
            {"filename": "scan.pdf", "category": "intermediate_transcript", "extraction_status": "partial", "fields": {"name": "Ali"}},
        ])
        status = get_document_status(profile, "intermediate_transcript")
        assert status["extraction_status"] == "partial"


class TestGetUploadedCategories:
    def test_empty_profile(self):
        assert get_uploaded_categories({}) == set()

    def test_from_records(self):
        profile = _profile_with_records([
            {"filename": "cnic.pdf", "category": "cnic_bform"},
            {"filename": "dom.pdf", "category": "domicile"},
        ])
        assert get_uploaded_categories(profile) == {"cnic_bform", "domicile"}

    def test_from_legacy_docs(self):
        profile = _legacy_profile(["FSc Transcript", "Matric Certificate"])
        cats = get_uploaded_categories(profile)
        assert "intermediate_transcript" in cats
        assert "matric_certificate" in cats


class TestDocumentExistsVsExtracted:
    def test_not_uploaded(self):
        profile = _profile_with_records([])
        uploaded, extracted = document_exists_vs_extracted(profile, "cnic_bform")
        assert uploaded is False
        assert extracted is False

    def test_uploaded_and_extracted(self):
        profile = _profile_with_records([
            {"filename": "cnic.pdf", "category": "cnic_bform", "extraction_status": "extracted"},
        ])
        uploaded, extracted = document_exists_vs_extracted(profile, "cnic_bform")
        assert uploaded is True
        assert extracted is True

    def test_uploaded_but_failed(self):
        profile = _profile_with_records([
            {"filename": "scan.pdf", "category": "cnic_bform", "extraction_status": "failed"},
        ])
        uploaded, extracted = document_exists_vs_extracted(profile, "cnic_bform")
        assert uploaded is True
        assert extracted is False

    def test_uploaded_partial_counts_as_extracted(self):
        profile = _profile_with_records([
            {"filename": "scan.pdf", "category": "intermediate_transcript", "extraction_status": "partial"},
        ])
        uploaded, extracted = document_exists_vs_extracted(profile, "intermediate_transcript")
        assert uploaded is True
        assert extracted is True
