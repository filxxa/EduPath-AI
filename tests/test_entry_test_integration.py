"""Comprehensive regression tests for entry test document integration.

Covers sections A through O:
  A  — test_names.py canonical name extraction
  B  — matches_test_name() fuzzy matching
  C  — eligibility.py exact-match bug fix
  D  — state.py build_checklist() fuzzy match
  E  — pipeline.py routing for entry_test_score
  F  — fields.py recognizes new test types
  G  — fields.py total score extraction
  H  — merging.py category filter
  I  — merging.py structured test_score_records
  J  — profile.py merge handles test_score_records
  K  — Profile dropdown data-driven options
  L  — Action Plan recognizes uploaded entry test
  M  — Backward compat with old {name: score} format
  N  — Merit calc still works with new data
  O  — Existing intermediate/matric routing unchanged
"""
from __future__ import annotations

import pytest

from backend.documents.models import ExtractedDocument, ExtractedField, ValidationResult
from backend.documents.fields import extract_test_score
from backend.documents.classification import classify_document
from backend.documents.merging import merge_documents
from backend.documents.pipeline import process_upload, _USER_ROUTED_CATEGORIES
from backend.profile import default_profile, merge_profile
from backend.test_names import get_test_name_options, matches_test_name


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_doc(
    filename: str = "test.txt",
    category: str | None = None,
    user_category: str | None = None,
    fields: list[tuple[str, object]] | None = None,
) -> ExtractedDocument:
    extracted = [
        ExtractedField(
            field=name, value=value, confidence=None,
            source_document=filename, extraction_method="regex",
        )
        for name, value in (fields or [])
    ]
    return ExtractedDocument(
        filename=filename,
        document_type="Test Document",
        canonical_category=category,
        validation=ValidationResult(),
        extraction_method="text",
        raw_text="test content",
        fields=extracted,
        user_category=user_category,
    )


# ── A: Canonical name extraction ─────────────────────────────────────────

class TestCanonicalNames:
    def test_returns_non_empty_list(self):
        options = get_test_name_options()
        assert isinstance(options, list)
        assert len(options) > 0

    def test_contains_known_tests(self):
        options = get_test_name_options()
        options_lower = [o.lower() for o in options]
        assert "sat" in options_lower
        assert "act" in options_lower
        assert "ecat 2026" in options_lower
        assert "nts-nat" in options_lower

    def test_excludes_no_ecat(self):
        options = get_test_name_options()
        options_lower = [o.lower() for o in options]
        assert "no ecat" not in options_lower

    def test_sorted_case_insensitive(self):
        options = get_test_name_options()
        assert options == sorted(options, key=str.lower)


# ── B: Fuzzy matching ────────────────────────────────────────────────────

class TestFuzzyMatching:
    def test_exact_match(self):
        assert matches_test_name({"SAT"}, "SAT / ACT / LCAT")

    def test_case_insensitive(self):
        assert matches_test_name({"sat"}, "SAT / ACT")

    def test_substring_match(self):
        assert matches_test_name({"ECAT"}, "ECAT 2026")

    def test_nts_nat_matches_nts_nat_ie(self):
        assert matches_test_name({"NTS-NAT"}, "NTS-NAT")

    def test_nts_nat_ie_matches(self):
        assert matches_test_name({"NTS NAT-IE"}, "FAST-NUCES / SAT / NTS NAT-IE")

    def test_no_match(self):
        assert not matches_test_name({"GRE"}, "SAT / ACT / LCAT")

    def test_empty_student_keys(self):
        assert not matches_test_name(set(), "SAT / ACT")

    def test_empty_admission_field(self):
        assert not matches_test_name({"SAT"}, "")

    def test_or_separator(self):
        assert matches_test_name({"SAT"}, "NET Engineering / ACT or SAT")

    def test_muet_matches(self):
        assert matches_test_name(
            {"MUET"}, "MUET Computer-Based Pre-Admission Test"
        )


# ── C: Eligibility bug fix ───────────────────────────────────────────────

class TestEligibilityFuzzyMatch:
    def test_sat_matches_fast_nuces_field(self):
        from backend.eligibility import check_eligibility

        profile = {
            "qualification": "FSc Pre-Engineering",
            "hssc_percentage": 85.0,
            "ssc_percentage": 90.0,
            "documents": ["Matriculation Certificate", "Academic Transcript (FSc/Intermediate)"],
            "test_scores": {"SAT": "1400"},
        }
        program = {
            "id": "bscs",
            "name": "BS Computer Science",
            "requirements": {
                "admission_test": "FAST-NUCES / SAT / NTS NAT-IE",
                "minimum_aggregate": 60.0,
                "required_documents": [
                    {"name": "Matriculation Certificate", "category": "matric_certificate"},
                    {"name": "Intermediate Transcript", "category": "intermediate_transcript"},
                ],
            },
        }
        result = check_eligibility(profile, program)
        assert not result.get("test_missing"), (
            "SAT should match 'FAST-NUCES / SAT / NTS NAT-IE'"
        )

    def test_missing_test_when_no_scores(self):
        from backend.eligibility import check_eligibility

        profile = {
            "qualification": "FSc Pre-Engineering",
            "hssc_percentage": 85.0,
            "ssc_percentage": 90.0,
            "documents": ["Matriculation Certificate", "Academic Transcript (FSc/Intermediate)"],
            "test_scores": {},
        }
        program = {
            "id": "bscs",
            "name": "BS Computer Science",
            "requirements": {
                "admission_test": "FAST-NUCES / SAT / NTS NAT-IE",
                "minimum_aggregate": 60.0,
                "required_documents": [
                    {"name": "Matriculation Certificate", "category": "matric_certificate"},
                    {"name": "Intermediate Transcript", "category": "intermediate_transcript"},
                ],
            },
        }
        result = check_eligibility(profile, program)
        assert result.get("test_missing")


# ── D: Checklist fuzzy match ─────────────────────────────────────────────

class TestChecklistFuzzyMatch:
    def test_checklist_marks_test_done_on_fuzzy_match(self, monkeypatch):
        import streamlit as st
        from backend.state import build_checklist, default_profile, set_selection, update_profile
        from backend.data_loader import load_universities

        # Mock session state
        session = {"student_profile": default_profile(), "parsed_docs": [],
                   "selected_university_id": "fast-nuces", "selected_program_id": "bs-cs",
                   "eligibility_result": None, "selected_program_with_university": None}
        monkeypatch.setattr(st, "session_state", session)

        # Set up profile with SAT score
        update_profile({"test_scores": {"SAT": "1400"}, "qualification": "FSc Pre-Engineering",
                       "ssc_percentage": 85.0, "hssc_percentage": 88.0}, source="manual")

        # Mock university data
        monkeypatch.setattr("backend.state.load_universities", lambda: {
            "universities": [{
                "id": "fast-nuces",
                "name": "FAST-NUCES",
                "programs": [{
                    "id": "bs-cs",
                    "name": "BS Computer Science",
                    "requirements": {
                        "admission_test": "FAST-NUCES / SAT / NTS NAT-IE",
                        "required_documents": [],
                    },
                }],
            }]
        })

        set_selection("fast-nuces", "bs-cs")

        items = build_checklist()
        test_items = [i for i in items if i["category"] == "test"]
        assert len(test_items) == 1
        assert test_items[0]["done"] is True


# ── E: Pipeline routing ──────────────────────────────────────────────────

class TestPipelineRouting:
    def test_entry_test_score_in_user_routed_categories(self):
        assert "entry_test_score" in _USER_ROUTED_CATEGORIES

    def test_existing_categories_still_routed(self):
        assert "intermediate_transcript" in _USER_ROUTED_CATEGORIES
        assert "matric_certificate" in _USER_ROUTED_CATEGORIES

    def test_user_selected_entry_test_routes_correctly(self):
        content = b"SAT Score: 1400\nTotal: 1600\nRoll No: 123456"
        doc = process_upload("sat_result.txt", content, user_category="entry_test_score")
        assert doc.user_category == "entry_test_score"
        ts = doc.field_value("test_score")
        assert ts is not None
        assert ts["test"] == "SAT"


# ── F: New test type recognition ─────────────────────────────────────────

class TestNewTestTypes:
    def test_muet_recognized(self):
        result = extract_test_score("MUET Pre-Admission Test\nScore: 85\nRoll No: 999")
        assert result is not None
        assert "MUET" in result["test"]

    def test_act_recognized(self):
        result = extract_test_score("ACT Test Result\nScore: 32")
        assert result is not None
        assert result["test"] == "ACT"

    def test_fast_nuces_recognized(self):
        result = extract_test_score("FAST-NUCES Entry Test\nScore: 78")
        assert result is not None
        assert "FAST" in result["test"]

    def test_nts_nat_recognized(self):
        result = extract_test_score("NTS-NAT Result\nScore: 89")
        assert result is not None
        assert "NTS" in result["test"]

    def test_ecat_with_year(self):
        result = extract_test_score("ECAT 2026 Result\nScore: 150")
        assert result is not None
        assert "ECAT" in result["test"]

    def test_nat_subtype_ie(self):
        result = extract_test_score("NTS NAT-IE Score: 90")
        assert result is not None
        assert "NAT" in result["test"]


# ── G: Total score extraction ────────────────────────────────────────────

class TestTotalScoreExtraction:
    def test_total_from_out_of(self):
        result = extract_test_score("SAT Score: 1400\nTotal: 1600")
        assert result is not None
        assert result["total_score"] == "1600"

    def test_total_from_fraction(self):
        result = extract_test_score("ECAT Score 150 / 200")
        assert result is not None
        assert result["total_score"] == "200"

    def test_no_total(self):
        result = extract_test_score("SAT Score: 1400")
        assert result is not None
        assert result["total_score"] is None


# ── H: Merging category filter ───────────────────────────────────────────

class TestMergingCategoryFilter:
    def test_only_entry_test_docs_contribute_scores(self):
        academic_doc = _make_doc(
            filename="fsc.txt",
            category="intermediate_transcript",
            fields=[("test_score", {"test": "NAT", "score": "90"})],
        )
        test_doc = _make_doc(
            filename="sat.txt",
            category="entry_test_score",
            fields=[("test_score", {"test": "SAT", "score": "1400"})],
        )
        proposal = merge_documents([academic_doc, test_doc])
        assert "SAT" in proposal.profile["test_scores"]
        assert "NAT" not in proposal.profile["test_scores"]

    def test_no_entry_test_docs_means_empty_scores(self):
        academic_doc = _make_doc(
            filename="fsc.txt",
            category="intermediate_transcript",
            fields=[("test_score", {"test": "NAT", "score": "90"})],
        )
        proposal = merge_documents([academic_doc])
        assert proposal.profile["test_scores"] == {}


# ── I: Structured test_score_records ─────────────────────────────────────

class TestStructuredRecords:
    def test_test_score_records_built(self):
        doc = _make_doc(
            filename="sat.txt",
            category="entry_test_score",
            fields=[
                ("test_score", {
                    "test": "SAT", "score": "1400",
                    "total_score": "1600", "test_date": "2026-03-15",
                    "roll_number": "123456",
                }),
            ],
        )
        proposal = merge_documents([doc])
        records = proposal.profile.get("test_score_records", [])
        assert len(records) == 1
        assert records[0]["test_name"] == "SAT"
        assert records[0]["score"] == "1400"
        assert records[0]["total_score"] == "1600"
        assert records[0]["source_document"] == "sat.txt"

    def test_empty_when_no_entry_test_docs(self):
        doc = _make_doc(
            filename="fsc.txt",
            category="intermediate_transcript",
            fields=[("test_score", {"test": "NAT", "score": "90"})],
        )
        proposal = merge_documents([doc])
        assert proposal.profile.get("test_score_records", []) == []


# ── J: Profile merge handles test_score_records ──────────────────────────

class TestProfileMergeRecords:
    def test_merge_adds_records(self):
        profile = default_profile()
        updates = {
            "test_scores": {"SAT": "1400"},
            "test_score_records": [
                {"test_name": "SAT", "score": "1400", "total_score": "1600"}
            ],
        }
        merged = merge_profile(profile, updates, source="ocr")
        assert merged["test_scores"]["SAT"] == "1400"
        assert len(merged["test_score_records"]) == 1

    def test_manual_overwrites_ocr_records(self):
        profile = default_profile()
        profile["test_score_records"] = [
            {"test_name": "SAT", "score": "1400", "source": "ocr"}
        ]
        profile["test_scores"] = {"SAT": "1400"}
        updates = {
            "test_scores": {"SAT": "1500"},
            "test_score_records": [
                {"test_name": "SAT", "score": "1500", "source": "manual"}
            ],
        }
        merged = merge_profile(profile, updates, source="manual")
        assert merged["test_scores"]["SAT"] == "1500"
        sat_records = [
            r for r in merged["test_score_records"] if r["test_name"] == "SAT"
        ]
        assert len(sat_records) == 1
        assert sat_records[0]["score"] == "1500"


# ── K: Profile dropdown options ──────────────────────────────────────────

class TestDropdownOptions:
    def test_options_are_strings(self):
        options = get_test_name_options()
        assert all(isinstance(o, str) for o in options)

    def test_options_contain_sat(self):
        options_lower = [o.lower() for o in get_test_name_options()]
        assert "sat" in options_lower

    def test_options_contain_lcat(self):
        options_lower = [o.lower() for o in get_test_name_options()]
        # LCAT appears as "LUMS Common Admission Test (LCAT)" in the data
        assert any("lcat" in opt for opt in options_lower)


# ── L: Action Plan recognizes uploaded entry test ────────────────────────

class TestActionPlanAwareness:
    def test_no_action_when_test_matches(self):
        from backend.state import build_next_actions

        profile = default_profile()
        profile["qualification"] = "FSc"
        profile["hssc_percentage"] = 85.0
        profile["test_scores"] = {"SAT": "1400"}
        profile["documents"] = [
            "Matriculation Certificate",
            "Academic Transcript (FSc/Intermediate)",
        ]

        import streamlit as st
        st.session_state["_profile"] = profile
        st.session_state["_selection"] = {
            "university_id": "fast-nuces",
            "program_id": "bscs",
            "program_display": "BS Computer Science",
            "eligibility": {
                "verdict": "ELIGIBLE",
                "test_missing": False,
                "admission_test": "FAST-NUCES / SAT / NTS NAT-IE",
                "missing_documents": [],
            },
        }

        actions = build_next_actions()
        test_actions = [
            a for a in actions
            if "test" in a.get("title", "").lower()
            or "register" in a.get("title", "").lower()
            or "verify" in a.get("title", "").lower()
        ]
        assert len(test_actions) == 0, (
            f"No test-related actions expected when test matches, got: {test_actions}"
        )


# ── M: Backward compatibility ────────────────────────────────────────────

class TestBackwardCompat:
    def test_old_format_still_works_in_eligibility(self):
        from backend.eligibility import check_eligibility

        profile = {
            "qualification": "FSc",
            "hssc_percentage": 85.0,
            "ssc_percentage": 90.0,
            "documents": [],
            "test_scores": {"SAT": "1400"},
        }
        program = {
            "id": "bscs",
            "name": "BS CS",
            "requirements": {
                "admission_test": "SAT",
                "minimum_aggregate": 60.0,
                "required_documents": [],
            },
        }
        result = check_eligibility(profile, program)
        assert not result.get("test_missing")

    def test_old_format_still_works_in_merit(self):
        from backend.merit import _resolve_test_score

        scores = {"SAT": "1400"}
        pct, name = _resolve_test_score(scores, "SAT / ACT")
        assert pct is not None
        assert name == "SAT"


# ── N: Merit calculation unchanged ───────────────────────────────────────

class TestMeritUnchanged:
    def test_resolve_test_score_with_compound_field(self):
        from backend.merit import _resolve_test_score

        scores = {"NTS NAT-IE": "90"}
        pct, name = _resolve_test_score(
            scores, "FAST-NUCES / SAT / NTS NAT-IE"
        )
        assert pct == 90.0
        assert name == "NTS NAT-IE"

    def test_resolve_test_score_fallback(self):
        from backend.merit import _resolve_test_score

        scores = {"SAT": "95"}
        pct, name = _resolve_test_score(scores, None)
        assert pct == 95.0


# ── O: Existing routing unchanged ────────────────────────────────────────

class TestExistingRoutingUnchanged:
    def test_intermediate_transcript_routes_correctly(self):
        content = b"FSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4"
        doc = process_upload("hssc.txt", content)
        assert doc.canonical_category == "intermediate_transcript"
        assert doc.field_value("aggregate") == 88.4

    def test_matric_certificate_routes_correctly(self):
        content = b"Matriculation Certificate\nSSC\nBISE Lahore\nMarks: 950/1100"
        doc = process_upload("matric.txt", content)
        assert doc.canonical_category == "matric_certificate"

    def test_user_override_still_works_for_intermediate(self):
        content = b"FSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4"
        doc = process_upload("scan.txt", content, user_category="intermediate_transcript")
        assert doc.user_category == "intermediate_transcript"
        assert doc.field_value("aggregate") == 88.4


# ── Classification hints ─────────────────────────────────────────────────

class TestClassificationHints:
    def test_muet_filename_classified(self):
        result = classify_document("muet_test_score.pdf")
        assert result["canonical_category"] == "entry_test_score"

    def test_act_filename_classified(self):
        result = classify_document("act_result.pdf")
        assert result["canonical_category"] == "entry_test_score"

    def test_nts_nat_filename_classified(self):
        result = classify_document("nts-nat_score.pdf")
        assert result["canonical_category"] == "entry_test_score"

    def test_content_hint_admission_test(self):
        result = classify_document(
            "scan_001.pdf",
            "Admission Test Score Card\nSAT Score: 1400"
        )
        assert result["canonical_category"] == "entry_test_score"
