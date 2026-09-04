"""Tests for upload category definitions and mappings."""
from __future__ import annotations

from backend.documents.categories import (
    CANONICAL_TO_UPLOAD,
    CATEGORY_TO_CANONICAL,
    DISPLAY_ORDER,
    MULTI_DOC_CATEGORIES,
    UPLOAD_CATEGORIES,
    UPLOAD_GROUPS,
)


class TestUploadCategories:
    def test_six_categories_defined(self):
        assert len(UPLOAD_CATEGORIES) == 6

    def test_all_required_categories_present(self):
        expected = {
            "intermediate_transcript",
            "matric_certificate",
            "entry_test_score",
            "cnic_bform",
            "domicile",
            "other",
        }
        assert set(UPLOAD_CATEGORIES.keys()) == expected

    def test_each_category_has_required_fields(self):
        for key, meta in UPLOAD_CATEGORIES.items():
            assert "label" in meta, f"{key} missing label"
            assert "canonical_category" in meta, f"{key} missing canonical_category"
            assert "allows_multiple" in meta, f"{key} missing allows_multiple"
            assert "group" in meta, f"{key} missing group"

    def test_canonical_category_matches_key(self):
        for key, meta in UPLOAD_CATEGORIES.items():
            assert meta["canonical_category"] == key


class TestMultiDocCategories:
    def test_entry_test_and_other_are_multi(self):
        assert "entry_test_score" in MULTI_DOC_CATEGORIES
        assert "other" in MULTI_DOC_CATEGORIES

    def test_academic_and_identity_are_single(self):
        assert "intermediate_transcript" not in MULTI_DOC_CATEGORIES
        assert "matric_certificate" not in MULTI_DOC_CATEGORIES
        assert "cnic_bform" not in MULTI_DOC_CATEGORIES
        assert "domicile" not in MULTI_DOC_CATEGORIES


class TestMappings:
    def test_category_to_canonical_is_identity(self):
        for key in UPLOAD_CATEGORIES:
            assert CATEGORY_TO_CANONICAL[key] == key

    def test_canonical_to_upload_round_trips(self):
        for key in UPLOAD_CATEGORIES:
            assert CANONICAL_TO_UPLOAD[key] == key

    def test_display_order_contains_all_categories(self):
        assert set(DISPLAY_ORDER) == set(UPLOAD_CATEGORIES.keys())

    def test_display_order_respects_group_ordering(self):
        academic_idx = DISPLAY_ORDER.index("intermediate_transcript")
        matric_idx = DISPLAY_ORDER.index("matric_certificate")
        entry_idx = DISPLAY_ORDER.index("entry_test_score")
        assert academic_idx < entry_idx
        assert matric_idx < entry_idx


class TestUploadGroups:
    def test_four_groups(self):
        assert len(UPLOAD_GROUPS) == 4

    def test_group_names(self):
        assert set(UPLOAD_GROUPS.keys()) == {
            "Academic",
            "Admission Test",
            "Identity & Residence",
            "Other",
        }

    def test_all_categories_in_some_group(self):
        grouped = {cat for cats in UPLOAD_GROUPS.values() for cat in cats}
        assert grouped == set(UPLOAD_CATEGORIES.keys())
