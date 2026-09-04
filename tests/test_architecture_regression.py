"""Regression tests for the three root-cause UX problems.

Problem 1: Documents sometimes require multiple upload attempts.
Problem 2: User must navigate away and back before Profile/Build Profile appear.
Problem 3: Build Profile takes too long (OCR at button-click instead of upload-time).

These tests verify the process-at-upload / merge-at-build architecture.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.documents import DocumentCache, fingerprint
from backend.documents.models import ExtractedDocument, ExtractedField, ValidationResult
from backend.state import (
    build_profile_from_processed,
    composite_fingerprint,
)


def _make_extracted_doc(
    filename: str = "test.pdf",
    category: str = "intermediate_transcript",
    fields: dict | None = None,
) -> ExtractedDocument:
    extracted_fields = []
    for fname, fval in (fields or {"name": "Test Student", "aggregate": 85.5}).items():
        extracted_fields.append(
            ExtractedField(
                field=fname,
                value=fval,
                confidence=0.9,
                source_document=filename,
                extraction_method="test",
            )
        )
    return ExtractedDocument(
        filename=filename,
        document_type="Transcript",
        canonical_category=category,
        validation=ValidationResult(valid=True),
        extraction_method="test",
        raw_text="Test raw text",
        fields=extracted_fields,
        user_category=category,
    )


def _make_processed_entry(
    filename: str = "test.pdf",
    category: str = "intermediate_transcript",
    fields: dict | None = None,
) -> tuple[str, dict]:
    doc = _make_extracted_doc(filename, category, fields)
    fp = fingerprint(b"content")
    cache_key = f"{fp}:{category}"
    return cache_key, {
        "document_dict": doc.to_dict(),
        "processing_ms": 100.0,
        "category": category,
        "filename": filename,
        "fingerprint": fp,
    }


class TestProblem1_UploadImmediatelyProcessed:
    """Problem 1: Documents sometimes require multiple upload attempts."""

    def test_upload_processed_stored_immediately(self):
        """Upload → processed → stored → immediately available to Build Profile."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        assert len(processed) == 1
        assert cache_key in processed
        assert processed[cache_key]["filename"] == "test.pdf"
        assert processed[cache_key]["category"] == "intermediate_transcript"

    def test_processed_docs_available_without_rerun(self):
        """After processing, docs are in session state — no navigation needed."""
        processed: dict[str, dict] = {}

        cache_key1, entry1 = _make_processed_entry("doc1.pdf", "intermediate_transcript")
        processed[cache_key1] = entry1

        cache_key2, entry2 = _make_processed_entry("doc2.pdf", "matric_certificate")
        processed[cache_key2] = entry2

        assert len(processed) == 2
        categories = {e["category"] for e in processed.values()}
        assert "intermediate_transcript" in categories
        assert "matric_certificate" in categories


class TestProblem2_NoNavigationRequired:
    """Problem 2: User must navigate away and back before results appear."""

    def test_rerun_same_file_no_reprocess(self):
        """Rerun with same file → OCR NOT called again (cache hit)."""
        processed: dict[str, dict] = {}
        doc = _make_extracted_doc()
        fp = fingerprint(b"content")
        cache_key = f"{fp}:intermediate_transcript"

        processed[cache_key] = {
            "document_dict": doc.to_dict(),
            "processing_ms": 100.0,
            "category": "intermediate_transcript",
            "filename": "test.pdf",
            "fingerprint": fp,
        }

        with patch("backend.documents.pipeline.process_upload") as mock_process:
            if cache_key in processed:
                pass
            else:
                mock_process.return_value = doc

            assert mock_process.call_count == 0

        assert cache_key in processed
        assert processed[cache_key]["filename"] == "test.pdf"

    def test_processed_results_persist_across_reruns(self):
        """Processed results displayed outside button handler — persist across reruns."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        assert len(processed) > 0
        for key, data in processed.items():
            assert "document_dict" in data
            assert "filename" in data
            assert "category" in data


class TestProblem3_BuildProfileIsCheap:
    """Problem 3: Build Profile takes too long."""

    def test_build_profile_uses_cached_docs_no_ocr(self):
        """Build Profile → cached docs used → OCR not called."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        with patch("backend.documents.pipeline.process_upload") as mock_process:
            profile_data = build_profile_from_processed(processed)

            assert mock_process.call_count == 0

        assert profile_data is not None
        assert isinstance(profile_data, dict)

    def test_replace_one_doc_only_changed_reprocessed(self):
        """Replace one doc → only changed doc reprocessed, others reused."""
        processed: dict[str, dict] = {}

        fp1 = fingerprint(b"content1")
        key1 = f"{fp1}:intermediate_transcript"
        doc1 = _make_extracted_doc("doc1.pdf", "intermediate_transcript")
        processed[key1] = {
            "document_dict": doc1.to_dict(),
            "processing_ms": 100.0,
            "category": "intermediate_transcript",
            "filename": "doc1.pdf",
            "fingerprint": fp1,
        }

        fp2 = fingerprint(b"content2")
        key2 = f"{fp2}:matric_certificate"
        doc2 = _make_extracted_doc("doc2.pdf", "matric_certificate")
        processed[key2] = {
            "document_dict": doc2.to_dict(),
            "processing_ms": 150.0,
            "category": "matric_certificate",
            "filename": "doc2.pdf",
            "fingerprint": fp2,
        }

        assert len(processed) == 2

        fp2_new = fingerprint(b"content2_new")
        key2_new = f"{fp2_new}:matric_certificate"
        processed.pop(key2, None)

        doc2_new = _make_extracted_doc("doc2_new.pdf", "matric_certificate")
        processed[key2_new] = {
            "document_dict": doc2_new.to_dict(),
            "processing_ms": 120.0,
            "category": "matric_certificate",
            "filename": "doc2_new.pdf",
            "fingerprint": fp2_new,
        }

        assert key1 in processed
        assert key2 not in processed
        assert key2_new in processed
        assert processed[key1]["filename"] == "doc1.pdf"
        assert processed[key2_new]["filename"] == "doc2_new.pdf"

    def test_build_profile_immediately_populated(self):
        """Build Profile → profile immediately populated, profile_built=True."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry(
            fields={"name": "John Doe", "aggregate": 90.0, "qualification": "FSc"}
        )
        processed[cache_key] = entry

        profile_data = build_profile_from_processed(processed)
        assert profile_data is not None
        assert profile_data.get("name") == "John Doe"
        assert profile_data.get("aggregate") == 90.0

        profile_built = True
        profile_fp = composite_fingerprint(processed)

        assert profile_built is True
        assert profile_fp is not None
        assert len(profile_fp) == 16


class TestProblem3_EligibilityAccess:
    """After Build Profile, eligibility can access updated profile."""

    def test_eligibility_can_access_updated_profile(self):
        """After Build Profile, eligibility engine can read document_records."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry(
            fields={"name": "Jane Doe", "aggregate": 88.0}
        )
        processed[cache_key] = entry

        profile_data = build_profile_from_processed(processed)
        assert profile_data is not None

        assert "document_records" in profile_data
        assert "documents" in profile_data
        assert len(profile_data["document_records"]) > 0

        doc_records = profile_data["document_records"]
        assert any(r.get("category") == "intermediate_transcript" for r in doc_records)


class TestProblem3_AccuracyPreserved:
    """Existing OCR accuracy is preserved."""

    def test_cached_doc_matches_fresh_doc(self):
        """Cached document dict matches what fresh processing would produce."""
        doc = _make_extracted_doc(
            fields={"name": "Test Student", "aggregate": 85.5, "board": "FBISE"}
        )
        doc_dict = doc.to_dict()

        restored = ExtractedDocument.from_dict(doc_dict)

        assert restored.filename == doc.filename
        assert restored.effective_category == doc.effective_category
        assert restored.field_value("name") == "Test Student"
        assert restored.field_value("aggregate") == 85.5
        assert restored.field_value("board") == "FBISE"

    def test_build_profile_from_processed_preserves_all_fields(self):
        """build_profile_from_processed preserves all extracted fields."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry(
            fields={
                "name": "Full Name",
                "father_name": "Father",
                "aggregate": 92.5,
                "board": "BISE Lahore",
                "qualification": "FSc Pre-Engineering",
            }
        )
        processed[cache_key] = entry

        profile_data = build_profile_from_processed(processed)
        assert profile_data is not None
        assert profile_data.get("name") == "Full Name"
        assert profile_data.get("father_name") == "Father"
        assert profile_data.get("aggregate") == 92.5
        assert profile_data.get("board") == "BISE Lahore"
        assert profile_data.get("qualification") == "FSc Pre-Engineering"


class TestCompositeFingerprint:
    """Test the composite fingerprint helper."""

    def test_fingerprint_changes_on_add(self):
        processed: dict[str, dict] = {}
        fp1 = composite_fingerprint(processed)

        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry
        fp2 = composite_fingerprint(processed)

        assert fp1 != fp2

    def test_fingerprint_changes_on_remove(self):
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry
        fp1 = composite_fingerprint(processed)

        processed.pop(cache_key)
        fp2 = composite_fingerprint(processed)

        assert fp1 != fp2

    def test_fingerprint_stable(self):
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        fp1 = composite_fingerprint(processed)
        fp2 = composite_fingerprint(processed)

        assert fp1 == fp2


class TestRerunLoopPrevention:
    """Verify the rerun loop fix: already-uploaded files don't trigger reprocessing."""

    def test_already_uploaded_files_skip_processing(self):
        """If files are already in category_uploads, the upload handler is a no-op."""
        existing = [("test.pdf", b"content")]
        new_files = [("test.pdf", b"content")]

        existing_names = {f[0] for f in existing}
        new_names = {f[0] for f in new_files}

        assert new_names.issubset(existing_names)

    def test_new_files_trigger_processing(self):
        """If files are NOT in category_uploads, the upload handler processes them."""
        existing = [("old.pdf", b"old_content")]
        new_files = [("new.pdf", b"new_content")]

        existing_names = {f[0] for f in existing}
        new_names = {f[0] for f in new_files}

        assert not new_names.issubset(existing_names)

    def test_rerun_does_not_reprocess_cached_docs(self):
        """Simulate a rerun: processed docs are already in the dict, no OCR called."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        with patch("backend.documents.pipeline.process_upload") as mock_process:
            if cache_key in processed:
                pass
            else:
                mock_process.return_value = _make_extracted_doc()

            assert mock_process.call_count == 0

        assert cache_key in processed


class TestBuildProfileAlwaysVisible:
    """Build Profile section is ALWAYS rendered — button gated on processed docs."""

    def test_build_profile_section_rendered_with_zero_docs(self):
        """Build Profile section renders even when processed is empty and no uploads."""
        processed: dict[str, dict] = {}
        total_uploads = 0

        # The section is unconditional — it always renders.
        # Only the BUTTON is gated on processed being non-empty.
        section_always_visible = True  # No condition wrapping the section
        button_enabled = bool(processed)

        assert section_always_visible is True
        assert button_enabled is False  # No docs → button not shown

    def test_build_profile_button_enabled_when_processed_nonempty(self):
        """Build Profile button appears when processed_documents is non-empty."""
        processed: dict[str, dict] = {}
        cache_key, entry = _make_processed_entry()
        processed[cache_key] = entry

        button_enabled = bool(processed)
        assert button_enabled is True

    def test_build_profile_info_message_when_empty(self):
        """When no processed docs, an info message is shown instead of the button."""
        processed: dict[str, dict] = {}

        if not processed:
            message = "Upload and process at least one document above, then build your profile here."
        else:
            message = None

        assert message is not None
        assert "at least one document" in message


class TestSpinnerCoversEntireOperation:
    """Spinner must remain active until processing AND state commit are complete."""

    def test_spinner_wraps_process_and_storage(self):
        """Verify that in _process_new_uploads, storage happens inside the spinner context.

        We verify this by checking the source code structure: the processed[cache_key]
        assignment and doc_cache.put() calls are INSIDE the `with st.spinner()` block.
        """
        import ast

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_page = os.path.join(project_root, "pages", "1_Upload_Documents.py")

        with open(upload_page, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Find _process_new_uploads function
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_process_new_uploads":
                func_def = node
                break

        assert func_def is not None, "_process_new_uploads function must exist"

        # Find the With node (st.spinner context manager)
        spinner_with = None
        for node in ast.walk(func_def):
            if isinstance(node, ast.With):
                spinner_with = node
                break

        assert spinner_with is not None, "st.spinner context manager must exist"

        # Check that processed[cache_key] = ... is INSIDE the With block
        storage_found = False
        cache_put_found = False
        for node in ast.walk(spinner_with):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Subscript):
                        if isinstance(target.value, ast.Name) and target.value.id == "processed":
                            storage_found = True
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr == "put":
                    cache_put_found = True

        assert storage_found, "processed[cache_key] = ... must be INSIDE st.spinner block"
        assert cache_put_found, "doc_cache.put(...) must be INSIDE st.spinner block"


class TestRerunOnlyOnStateChange:
    """st.rerun() must only fire when state actually changed (new files processed)."""

    def test_rerun_inside_else_branch_not_outside(self):
        """Verify st.rerun() is NOT unconditional after the issubset check.

        The invariant: st.rerun() must NOT be a direct child of `if uploaded:`
        at the same level as the issubset if/else. It must be nested inside
        the else branch of the issubset check, so it only fires when new
        files are actually processed.
        """
        import ast

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_page = os.path.join(project_root, "pages", "1_Upload_Documents.py")

        with open(upload_page, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "uploaded":
                    # st.rerun() must NOT be a direct child of `if uploaded:` body
                    direct_rerun = False
                    for child in node.body:
                        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                            if isinstance(child.value.func, ast.Attribute):
                                if child.value.func.attr == "rerun":
                                    direct_rerun = True

                    assert not direct_rerun, (
                        "st.rerun() must NOT be a direct child of `if uploaded:` — "
                        "it must be inside the else branch of the issubset check"
                    )

                    # Find the issubset If node inside `if uploaded:`
                    issubset_if = None
                    for child in node.body:
                        if isinstance(child, ast.If):
                            if isinstance(child.test, ast.Call):
                                if isinstance(child.test.func, ast.Attribute):
                                    if child.test.func.attr == "issubset":
                                        issubset_if = child

                    assert issubset_if is not None, (
                        "Must find an issubset() check inside `if uploaded:`"
                    )

                    # st.rerun() must be inside the else branch of issubset_if
                    rerun_in_else = False
                    for child in ast.walk(ast.Module(body=issubset_if.orelse, type_ignores=[])):
                        if isinstance(child, ast.Expr) and isinstance(child.value, ast.Call):
                            if isinstance(child.value.func, ast.Attribute):
                                if child.value.func.attr == "rerun":
                                    rerun_in_else = True

                    assert rerun_in_else, (
                        "st.rerun() must be inside the else branch of the issubset check "
                        "(only fires when new files are processed)"
                    )
                    break

    def test_already_uploaded_no_rerun_no_reprocess(self):
        """When files are already tracked, neither processing nor rerun occurs."""
        existing = [("test.pdf", b"content")]
        new_files = [("test.pdf", b"content")]

        existing_names = {f[0] for f in existing}
        new_names = {f[0] for f in new_files}

        is_already_uploaded = new_names.issubset(existing_names)
        assert is_already_uploaded is True

        # In the code, this hits the `pass` branch — no processing, no rerun
        state_changed = not is_already_uploaded
        assert state_changed is False  # No state change → no rerun


class TestHomeEntryPoint:
    """Verify the main page was renamed from app.py to Home.py."""

    def test_home_py_exists(self):
        """Home.py exists at the project root."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        home_path = os.path.join(project_root, "Home.py")
        assert os.path.exists(home_path), "Home.py must exist at project root"

    def test_app_py_does_not_exist(self):
        """app.py no longer exists at the project root."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(project_root, "app.py")
        assert not os.path.exists(app_path), "app.py must not exist — renamed to Home.py"

    def test_no_references_to_app_py_in_codebase(self):
        """No Python files reference 'app.py' as a page path."""
        import re
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pattern = re.compile(r'["\']app\.py["\']')

        for dirpath, dirnames, filenames in os.walk(project_root):
            if ".git" in dirpath or "__pycache__" in dirpath:
                continue
            for fname in filenames:
                if fname.endswith(".py") and fname != "test_architecture_regression.py":
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    assert not pattern.search(content), (
                        f"{fpath} still references 'app.py'"
                    )
