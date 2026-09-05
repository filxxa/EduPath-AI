"""Regression tests for three fixes:

1. PNG/JPG upload status indicator — successful images show green, not yellow.
2. MUET HSSC requirement recognition — intermediate docs satisfy HSC-I/II/DAE.
3. "Other" documents labelable — labels flow through to eligibility.
"""
from __future__ import annotations

import pytest

from backend.documents.models import ExtractedDocument, ValidationResult, ExtractedField
from backend.documents.pipeline import process_upload
from backend.documents.merging import _build_document_records
from backend.eligibility import (
    _normalize_document,
    check_eligibility,
)
from backend.document_status import has_document, get_uploaded_categories


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(
    filename: str = "test.pdf",
    category: str | None = None,
    user_category: str | None = None,
    document_label: str | None = None,
    extraction_method: str = "text",
    raw_text: str = "some text",
    fields: list[ExtractedField] | None = None,
    valid: bool = True,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename,
        document_type="Supporting Document",
        canonical_category=category,
        user_category=user_category,
        document_label=document_label,
        validation=ValidationResult(
            valid=valid,
            errors=errors or [],
            warnings=warnings or [],
        ),
        extraction_method=extraction_method,
        raw_text=raw_text,
        fields=fields or [],
    )


# ---------------------------------------------------------------------------
# Issue #1: PNG/JPG status indicator
# ---------------------------------------------------------------------------


class TestImageStatusIndicator:
    """Successful image processing should not produce validation warnings
    just because auto-classification disagrees with user selection."""

    def test_auto_classification_mismatch_not_in_validation_warnings(self):
        """When user selects 'intermediate_transcript' but auto-classification
        detects something else, the mismatch should NOT appear in validation.warnings."""
        content = b"fake image content"
        # Use a generic filename that won't trigger strong filename hints
        doc = process_upload(
            "scan_001.png",
            content,
            user_category="intermediate_transcript",
        )
        mismatch_warnings = [
            w for w in doc.validation.warnings
            if "Auto-classification" in w
        ]
        assert mismatch_warnings == [], (
            f"Auto-classification mismatch should not be a validation warning, "
            f"found: {mismatch_warnings}"
        )

    def test_successful_image_no_warnings(self):
        """A valid image with user category should have no warnings
        (unless OCR confidence is genuinely low)."""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        doc = process_upload(
            "marksheet.png",
            content,
            user_category="intermediate_transcript",
        )
        auto_mismatch = [
            w for w in doc.validation.warnings
            if "Auto-classification" in w or "categorized" in w
        ]
        assert auto_mismatch == []

    def test_pipeline_still_logs_mismatch(self, caplog):
        """The mismatch should still be logged for diagnostics."""
        import logging
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with caplog.at_level(logging.INFO, logger="backend.documents.pipeline"):
            doc = process_upload(
                "fsc_marksheet.png",
                content,
                user_category="entry_test_score",
            )
        mismatch_logs = [
            r.message for r in caplog.records
            if "auto-classification" in r.message.lower()
        ]
        assert len(mismatch_logs) > 0, "Mismatch should be logged at INFO level"


# ---------------------------------------------------------------------------
# Issue #2: MUET HSSC requirement recognition
# ---------------------------------------------------------------------------


class TestMuetHsscRecognition:
    """Documents uploaded as intermediate_transcript should satisfy
    MUET's 'HSC-I / HSC-II / DAE / Equivalent Certificate' requirement."""

    def test_normalize_muet_requirement(self):
        """The MUET requirement string should normalize to intermediate_transcript."""
        result = _normalize_document("HSC-I / HSC-II / DAE / Equivalent Certificate")
        assert result == "intermediate_transcript", (
            f"Expected 'intermediate_transcript', got '{result}'"
        )

    def test_eligibility_with_intermediate_transcript_record(self):
        """A student with an intermediate_transcript document record should
        satisfy the MUET HSC requirement."""
        profile = {
            "qualification": "FSc Pre-Engineering",
            "aggregate": 75.0,
            "documents": [],
            "test_scores": {},
            "document_records": [
                {
                    "filename": "fsc_transcript.pdf",
                    "category": "intermediate_transcript",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
        }
        program = {
            "requirements": {
                "qualification": ["FSc Pre-Engineering"],
                "minimum_aggregate": 60.0,
                "required_documents": [
                    {
                        "name": "HSC-I / HSC-II / DAE / Equivalent Certificate",
                        "required": True,
                    },
                ],
            },
        }
        result = check_eligibility(
            profile, program,
            document_records=profile["document_records"],
        )
        missing = [d["name"] for d in result.get("missing_documents", [])]
        assert "HSC-I / HSC-II / DAE / Equivalent Certificate" not in missing

    def test_eligibility_with_labeled_other_document(self):
        """An 'other' document labeled 'FSC Transcript' should also satisfy
        the intermediate_transcript requirement."""
        profile = {
            "qualification": "FSc Pre-Engineering",
            "aggregate": 75.0,
            "documents": [],
            "test_scores": {},
            "document_records": [
                {
                    "filename": "scan.pdf",
                    "category": "other",
                    "document_label": "FSC Transcript",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
        }
        program = {
            "requirements": {
                "qualification": ["FSc Pre-Engineering"],
                "minimum_aggregate": 60.0,
                "required_documents": [
                    {
                        "name": "HSC-I / HSC-II / DAE / Equivalent Certificate",
                        "required": True,
                    },
                ],
            },
        }
        result = check_eligibility(
            profile, program,
            document_records=profile["document_records"],
        )
        missing = [d["name"] for d in result.get("missing_documents", [])]
        assert "HSC-I / HSC-II / DAE / Equivalent Certificate" not in missing


# ---------------------------------------------------------------------------
# Issue #3: "Other" documents labelable
# ---------------------------------------------------------------------------


class TestOtherDocumentLabeling:
    """Documents categorized as 'other' should be labelable, and the label
    should flow through to eligibility checking."""

    def test_normalize_character_certificate(self):
        """'Character Certificate' should normalize to character_certificate."""
        result = _normalize_document("Character Certificate")
        assert result == "character_certificate"

    def test_normalize_bonafide(self):
        """'Bonafide Certificate' should normalize to bonafide."""
        result = _normalize_document("Bonafide Certificate")
        assert result == "bonafide"

    def test_normalize_prc(self):
        """'PRC' should normalize to permanent_residence_certificate."""
        result = _normalize_document("PRC")
        assert result == "permanent_residence_certificate"

    def test_normalize_domicile_from_label(self):
        """'Domicile Certificate' should normalize to domicile."""
        result = _normalize_document("Domicile Certificate")
        assert result == "domicile"

    def test_has_document_with_label(self):
        """has_document() should find a document by its label even if category is 'other'."""
        profile = {
            "document_records": [
                {
                    "filename": "scan.pdf",
                    "category": "other",
                    "document_label": "Character Certificate",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
            "documents": [],
        }
        assert has_document(profile, "character_certificate") is True

    def test_has_document_domicile_via_label(self):
        """An 'other' document labeled 'Domicile Certificate' satisfies domicile."""
        profile = {
            "document_records": [
                {
                    "filename": "doc.pdf",
                    "category": "other",
                    "document_label": "Domicile Certificate",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
            "documents": [],
        }
        assert has_document(profile, "domicile") is True

    def test_get_uploaded_categories_includes_labels(self):
        """get_uploaded_categories() should include label-derived categories."""
        profile = {
            "document_records": [
                {
                    "filename": "scan.pdf",
                    "category": "other",
                    "document_label": "Character Certificate",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
            "documents": [],
        }
        cats = get_uploaded_categories(profile)
        assert "character_certificate" in cats
        assert "other" in cats

    def test_eligibility_with_labeled_other_document(self):
        """Eligibility should recognize a labeled 'other' document."""
        profile = {
            "qualification": "FSc Pre-Engineering",
            "aggregate": 75.0,
            "documents": [],
            "test_scores": {},
            "document_records": [
                {
                    "filename": "char_cert.pdf",
                    "category": "other",
                    "document_label": "Character Certificate",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
        }
        program = {
            "requirements": {
                "qualification": ["FSc Pre-Engineering"],
                "minimum_aggregate": 60.0,
                "required_documents": [
                    {
                        "name": "Character Certificate",
                        "required": True,
                    },
                ],
            },
        }
        result = check_eligibility(
            profile, program,
            document_records=profile["document_records"],
        )
        missing = [d["name"] for d in result.get("missing_documents", [])]
        assert "Character Certificate" not in missing

    def test_label_case_insensitive(self):
        """Label matching should be case-insensitive."""
        assert _normalize_document("CHARACTER CERTIFICATE") == "character_certificate"
        assert _normalize_document("character certificate") == "character_certificate"
        assert _normalize_document("Character  Certificate") == "character_certificate"

    def test_label_whitespace_tolerance(self):
        """Label matching should tolerate extra whitespace."""
        assert _normalize_document("  Character   Certificate  ") == "character_certificate"

    def test_document_model_serialization(self):
        """document_label should survive to_dict/from_dict round-trip."""
        doc = _make_doc(document_label="Character Certificate", category="other")
        d = doc.to_dict()
        assert d["document_label"] == "Character Certificate"
        restored = ExtractedDocument.from_dict(d)
        assert restored.document_label == "Character Certificate"

    def test_merging_carries_label(self):
        """_build_document_records should include document_label."""
        from backend.documents.merging import _build_document_records

        doc = _make_doc(
            filename="char.pdf",
            category="other",
            user_category="other",
            document_label="Character Certificate",
        )
        records = _build_document_records([doc])
        assert len(records) == 1
        assert records[0]["document_label"] == "Character Certificate"
        assert records[0]["category"] == "other"

    def test_none_label_handled_safely(self):
        """None label values should not cause AttributeError."""
        doc = _make_doc(
            filename="unknown.pdf",
            category="other",
            user_category="other",
            document_label=None,
        )
        records = _build_document_records([doc])
        assert len(records) == 1
        # None label should be preserved as None or empty, not cause errors
        assert records[0].get("document_label") in (None, "")
        # has_document should not crash with None label
        profile = {"document_records": records}
        assert not has_document(profile, "character_certificate")


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Existing functionality should not regress."""

    def test_non_other_documents_unaffected(self):
        """Documents with specific categories should not be affected by label logic."""
        profile = {
            "document_records": [
                {
                    "filename": "fsc.pdf",
                    "category": "intermediate_transcript",
                    "extraction_status": "extracted",
                    "fields": {},
                },
            ],
            "documents": [],
        }
        assert has_document(profile, "intermediate_transcript") is True
        cats = get_uploaded_categories(profile)
        assert "intermediate_transcript" in cats

    def test_legacy_documents_still_work(self):
        """Legacy documents list (without document_records) should still work."""
        profile = {
            "document_records": [],
            "documents": ["Character Certificate"],
        }
        assert has_document(profile, "character_certificate") is True

    def test_existing_document_aliases_preserved(self):
        """Existing document aliases should still normalize correctly."""
        assert _normalize_document("FSC Transcript") == "intermediate_transcript"
        assert _normalize_document("Matric Marksheet") == "matric_certificate"
        assert _normalize_document("SAT Score Report") == "entry_test_score"
        assert _normalize_document("CNIC") == "cnic_bform"
        assert _normalize_document("Domicile") == "domicile"
