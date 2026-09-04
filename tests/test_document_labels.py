"""Tests for document labeling / user override (Fix 3)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.eligibility import _student_document_categories


# ── _student_document_categories with label_overrides ──────────────

class TestStudentDocumentCategoriesWithOverrides:
    def test_no_overrides_uses_auto_classification(self):
        docs = ["FSc Transcript", "Matric Certificate"]
        cats = _student_document_categories(docs)
        assert "intermediate_transcript" in cats
        assert "matric_certificate" in cats

    def test_override_replaces_auto_classification(self):
        docs = ["scan_001.pdf"]
        cats_no_override = _student_document_categories(docs)
        assert len(cats_no_override) == 0

        cats_with_override = _student_document_categories(
            docs, label_overrides={"scan_001.pdf": "cnic_bform"}
        )
        assert "cnic_bform" in cats_with_override

    def test_override_for_known_document(self):
        docs = ["FSc Transcript"]
        cats = _student_document_categories(
            docs, label_overrides={"FSc Transcript": "entry_test_score"}
        )
        assert "entry_test_score" in cats
        assert "intermediate_transcript" not in cats

    def test_empty_overrides_dict(self):
        docs = ["Matric Certificate"]
        cats = _student_document_categories(docs, label_overrides={})
        assert "matric_certificate" in cats

    def test_none_overrides(self):
        docs = ["Matric Certificate"]
        cats = _student_document_categories(docs, label_overrides=None)
        assert "matric_certificate" in cats

    def test_multiple_overrides(self):
        docs = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
        overrides = {
            "doc1.pdf": "matric_certificate",
            "doc2.pdf": "intermediate_transcript",
            "doc3.pdf": "cnic_bform",
        }
        cats = _student_document_categories(docs, label_overrides=overrides)
        assert cats == {"matric_certificate", "intermediate_transcript", "cnic_bform"}

    def test_partial_overrides(self):
        docs = ["FSc Transcript", "unknown_scan.pdf"]
        overrides = {"unknown_scan.pdf": "domicile"}
        cats = _student_document_categories(docs, label_overrides=overrides)
        assert "intermediate_transcript" in cats
        assert "domicile" in cats


# ── State helpers ──────────────────────────────────────────────────

class TestDocumentLabelStateHelpers:
    @pytest.fixture
    def mock_session_state(self):
        state = {"document_labels": {}}
        with patch("backend.state.st") as mock_st:
            mock_st.session_state = state
            yield mock_st, state

    def test_get_document_labels_empty(self, mock_session_state):
        from backend.state import get_document_labels
        mock_st, state = mock_session_state
        labels = get_document_labels()
        assert labels == {}

    def test_set_document_label(self, mock_session_state):
        from backend.state import set_document_label, get_document_labels
        mock_st, state = mock_session_state
        set_document_label("test.pdf", "cnic_bform")
        labels = get_document_labels()
        assert labels["test.pdf"] == "cnic_bform"

    def test_set_document_label_clear(self, mock_session_state):
        from backend.state import set_document_label, get_document_labels
        mock_st, state = mock_session_state
        set_document_label("test.pdf", "cnic_bform")
        set_document_label("test.pdf", None)
        labels = get_document_labels()
        assert "test.pdf" not in labels

    def test_get_effective_category_user_label(self, mock_session_state):
        from backend.state import set_document_label, get_effective_category
        mock_st, state = mock_session_state
        set_document_label("test.pdf", "domicile")
        assert get_effective_category("test.pdf", "intermediate_transcript") == "domicile"

    def test_get_effective_category_fallback_to_auto(self, mock_session_state):
        from backend.state import get_effective_category
        mock_st, state = mock_session_state
        assert get_effective_category("test.pdf", "intermediate_transcript") == "intermediate_transcript"

    def test_get_effective_category_no_label_no_auto(self, mock_session_state):
        from backend.state import get_effective_category
        mock_st, state = mock_session_state
        assert get_effective_category("test.pdf", None) is None


# ── Backward compatibility for old profiles ─────────────────────────

class TestBackwardCompatOldProfiles:
    """Old profiles without document_records must still work via legacy path."""

    def test_has_document_with_legacy_documents_list(self):
        from backend.document_status import has_document

        profile = {
            "documents": ["Academic Transcript (FSc/Intermediate)"],
            "document_records": [],
        }
        assert has_document(profile, "intermediate_transcript") is True

    def test_has_document_returns_false_for_missing_category(self):
        from backend.document_status import has_document

        profile = {
            "documents": ["CNIC / B-Form"],
            "document_records": [],
        }
        assert has_document(profile, "intermediate_transcript") is False
        assert has_document(profile, "cnic_bform") is True

    def test_has_document_with_no_documents_at_all(self):
        from backend.document_status import has_document

        profile = {"documents": [], "document_records": []}
        assert has_document(profile, "intermediate_transcript") is False

    def test_get_uploaded_categories_legacy_fallback(self):
        from backend.document_status import get_uploaded_categories

        profile = {
            "documents": [
                "Academic Transcript (FSc/Intermediate)",
                "CNIC / B-Form",
            ],
            "document_records": [],
        }
        cats = get_uploaded_categories(profile)
        assert "intermediate_transcript" in cats
        assert "cnic_bform" in cats

    def test_document_exists_vs_extracted_with_records(self):
        from backend.document_status import document_exists_vs_extracted

        profile = {
            "documents": [],
            "document_records": [
                {
                    "filename": "hssc.pdf",
                    "category": "intermediate_transcript",
                    "extraction_status": "extracted",
                    "fields": {"aggregate": 88.4},
                }
            ],
        }
        uploaded, extracted = document_exists_vs_extracted(
            profile, "intermediate_transcript"
        )
        assert uploaded is True
        assert extracted is True

    def test_document_exists_vs_extracted_failed_extraction(self):
        from backend.document_status import document_exists_vs_extracted

        profile = {
            "documents": [],
            "document_records": [
                {
                    "filename": "scan.pdf",
                    "category": "intermediate_transcript",
                    "extraction_status": "failed",
                    "fields": {},
                }
            ],
        }
        uploaded, extracted = document_exists_vs_extracted(
            profile, "intermediate_transcript"
        )
        assert uploaded is True
        assert extracted is False

    def test_document_records_take_priority_over_legacy(self):
        from backend.document_status import has_document

        profile = {
            "documents": ["CNIC / B-Form"],
            "document_records": [
                {
                    "filename": "hssc.pdf",
                    "category": "intermediate_transcript",
                    "extraction_status": "extracted",
                    "fields": {},
                }
            ],
        }
        assert has_document(profile, "intermediate_transcript") is True
        assert has_document(profile, "cnic_bform") is False

    def test_get_document_status_empty_profile(self):
        from backend.document_status import get_document_status

        profile = {"documents": [], "document_records": []}
        status = get_document_status(profile, "intermediate_transcript")
        assert status["uploaded"] is False
        assert status["extraction_status"] == "none"
