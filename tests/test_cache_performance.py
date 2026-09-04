"""Regression tests for SHA-256 content-hash document caching.

Scenarios covered:
  A. First processing of a new document is a cache miss (full processing).
  B. Second call with the same bytes is a cache hit (no re-processing).
  C. Changed content (different SHA-256) triggers re-processing.
  D. Cache survives across multiple process_uploads_cached calls (rerun safety).
  E. Multiple different documents are each processed exactly once.
  F. Cached results are identical to uncached results (accuracy preserved).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.documents.cache import (
    CacheStats,
    DocumentCache,
    fingerprint,
    process_uploads_cached,
)
from backend.documents.models import ExtractedDocument
from backend.documents.pipeline import process_upload

INTERMEDIATE_CONTENT = (
    b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4\nNAT Score: 89"
)
CNIC_CONTENT = b"Name: Ali Hassan\nCNIC 12345"
MATRIC_CONTENT = b"Name: Ali Hassan\nBISE Lahore\nAggregate: 92.0"


class TestFingerprint:
    def test_same_bytes_same_hash(self) -> None:
        assert fingerprint(b"hello") == fingerprint(b"hello")

    def test_different_bytes_different_hash(self) -> None:
        assert fingerprint(b"hello") != fingerprint(b"world")

    def test_returns_64_char_hex(self) -> None:
        h = fingerprint(b"test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestDocumentCache:
    def test_put_and_get(self) -> None:
        cache = DocumentCache()
        doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)

        cache.put(INTERMEDIATE_CONTENT, None, doc, 42.0)
        entry = cache.get(INTERMEDIATE_CONTENT, None)

        assert entry is not None
        assert entry.cached is True
        assert entry.processing_ms == 42.0
        assert entry.document_dict["filename"] == "hssc.txt"

    def test_get_returns_none_on_miss(self) -> None:
        cache = DocumentCache()
        assert cache.get(b"unknown", None) is None

    def test_user_category_affects_cache_key(self) -> None:
        cache = DocumentCache()
        doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)

        cache.put(INTERMEDIATE_CONTENT, "intermediate_transcript", doc, 10.0)

        assert cache.get(INTERMEDIATE_CONTENT, None) is None
        assert cache.get(INTERMEDIATE_CONTENT, "intermediate_transcript") is not None

    def test_invalidate_removes_entry(self) -> None:
        cache = DocumentCache()
        doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)
        cache.put(INTERMEDIATE_CONTENT, None, doc, 10.0)

        cache.invalidate(INTERMEDIATE_CONTENT, None)

        assert cache.get(INTERMEDIATE_CONTENT, None) is None

    def test_clear_empties_cache(self) -> None:
        cache = DocumentCache()
        doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)
        cache.put(INTERMEDIATE_CONTENT, None, doc, 10.0)
        assert len(cache) == 1

        cache.clear()
        assert len(cache) == 0


class TestScenarioA_FirstProcessingIsCacheMiss:
    """First processing of a new document must be a cache miss."""

    def test_new_document_is_miss(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        docs, stats = process_uploads_cached(uploads, cache=cache)

        assert stats.misses == 1
        assert stats.hits == 0
        assert len(docs) == 1
        assert docs[0].field_value("name") == "Ali Hassan"

    def test_first_processing_calls_process_upload(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        with patch(
            "backend.documents.cache.process_upload",
            wraps=process_upload,
        ) as mock_process:
            docs, stats = process_uploads_cached(uploads, cache=cache)

        assert mock_process.call_count == 1
        assert stats.misses == 1


class TestScenarioB_SecondBuildIsCacheHit:
    """Building profile again with the same document must NOT re-process."""

    def test_second_call_is_cache_hit(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        process_uploads_cached(uploads, cache=cache)
        docs, stats = process_uploads_cached(uploads, cache=cache)

        assert stats.hits == 1
        assert stats.misses == 0
        assert len(docs) == 1

    def test_cached_result_not_reprocessed(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        process_uploads_cached(uploads, cache=cache)

        with patch(
            "backend.documents.cache.process_upload",
        ) as mock_process:
            docs, stats = process_uploads_cached(uploads, cache=cache)

        mock_process.assert_not_called()
        assert stats.hits == 1

    def test_cached_result_has_same_fields(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        first_docs, _ = process_uploads_cached(uploads, cache=cache)
        second_docs, _ = process_uploads_cached(uploads, cache=cache)

        assert first_docs[0].field_value("name") == second_docs[0].field_value("name")
        assert first_docs[0].field_value("aggregate") == second_docs[0].field_value("aggregate")
        assert first_docs[0].canonical_category == second_docs[0].canonical_category


class TestScenarioC_ChangedContentReprocesses:
    """A document with different content (different SHA-256) must be re-processed."""

    def test_different_content_is_cache_miss(self) -> None:
        cache = DocumentCache()
        original = [("hssc.txt", INTERMEDIATE_CONTENT)]
        process_uploads_cached(original, cache=cache)

        changed_content = b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 75.0"
        changed = [("hssc.txt", changed_content)]
        _, stats = process_uploads_cached(changed, cache=cache)

        assert stats.misses == 1
        assert stats.hits == 0

    def test_different_content_extracts_new_values(self) -> None:
        cache = DocumentCache()
        original = [("hssc.txt", INTERMEDIATE_CONTENT)]
        process_uploads_cached(original, cache=cache)

        changed_content = b"Name: Sara Khan\nFSc Pre-Medical\nBISE Karachi\nAggregate: 75.0"
        changed = [("hssc.txt", changed_content)]
        docs, _ = process_uploads_cached(changed, cache=cache)

        assert docs[0].field_value("name") == "Sara Khan"
        assert docs[0].field_value("aggregate") == 75.0

    def test_same_filename_different_bytes_different_fingerprint(self) -> None:
        assert fingerprint(INTERMEDIATE_CONTENT) != fingerprint(
            b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 75.0"
        )


class TestScenarioD_RerunsDontDuplicate:
    """Multiple calls (simulating Streamlit reruns) must not duplicate processing."""

    def test_five_reruns_only_one_processing(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        total_processed = 0
        for _ in range(5):
            _, stats = process_uploads_cached(uploads, cache=cache)
            total_processed += stats.misses

        assert total_processed == 1

    def test_cache_store_survives_across_cache_instances(self) -> None:
        """Simulates Streamlit rerun where DocumentCache is re-created from session state."""
        store: dict = {}
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        cache1 = DocumentCache(store)
        process_uploads_cached(uploads, cache=cache1)

        cache2 = DocumentCache(store)
        _, stats = process_uploads_cached(uploads, cache=cache2)

        assert stats.hits == 1
        assert stats.misses == 0


class TestScenarioE_MultipleDocumentsEachProcessedOnce:
    """Multiple different documents must each be processed exactly once."""

    def test_three_documents_three_misses(self) -> None:
        cache = DocumentCache()
        uploads = [
            ("hssc.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", CNIC_CONTENT),
            ("matric.txt", MATRIC_CONTENT),
        ]

        _, stats = process_uploads_cached(uploads, cache=cache)

        assert stats.misses == 3
        assert stats.hits == 0
        assert len(stats.per_document) == 3

    def test_second_batch_all_hits(self) -> None:
        cache = DocumentCache()
        uploads = [
            ("hssc.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", CNIC_CONTENT),
            ("matric.txt", MATRIC_CONTENT),
        ]

        process_uploads_cached(uploads, cache=cache)
        _, stats = process_uploads_cached(uploads, cache=cache)

        assert stats.hits == 3
        assert stats.misses == 0

    def test_partial_change_only_reprocesses_changed(self) -> None:
        cache = DocumentCache()
        uploads = [
            ("hssc.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", CNIC_CONTENT),
        ]
        process_uploads_cached(uploads, cache=cache)

        changed_cnic = b"Name: Ali Hassan\nCNIC 99999"
        changed_uploads = [
            ("hssc.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", changed_cnic),
        ]
        _, stats = process_uploads_cached(changed_uploads, cache=cache)

        assert stats.hits == 1
        assert stats.misses == 1

        hssc_entry = next(e for e in stats.per_document if e["filename"] == "hssc.txt")
        cnic_entry = next(e for e in stats.per_document if e["filename"] == "cnic.txt")
        assert hssc_entry["cache_hit"] is True
        assert cnic_entry["cache_hit"] is False


class TestScenarioF_AccuracyPreserved:
    """Cached results must be identical to fresh processing — no accuracy loss."""

    def test_cached_matches_fresh_for_all_fields(self) -> None:
        fresh_doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)

        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]
        process_uploads_cached(uploads, cache=cache)
        cached_docs, _ = process_uploads_cached(uploads, cache=cache)

        cached_doc = cached_docs[0]

        assert cached_doc.field_value("name") == fresh_doc.field_value("name")
        assert cached_doc.field_value("qualification") == fresh_doc.field_value("qualification")
        assert cached_doc.field_value("board") == fresh_doc.field_value("board")
        assert cached_doc.field_value("aggregate") == fresh_doc.field_value("aggregate")
        assert cached_doc.canonical_category == fresh_doc.canonical_category
        assert cached_doc.extraction_method == fresh_doc.extraction_method
        assert cached_doc.validation.valid == fresh_doc.validation.valid

    def test_cached_serialization_round_trip(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]
        process_uploads_cached(uploads, cache=cache)
        cached_docs, _ = process_uploads_cached(uploads, cache=cache)

        doc = cached_docs[0]
        serialized = doc.to_dict()
        restored = ExtractedDocument.from_dict(serialized)

        assert restored.field_value("name") == "Ali Hassan"
        assert restored.field_value("aggregate") == 88.4

    def test_no_cache_produces_same_results_as_uncached(self) -> None:
        """Results with cache=None must match results without caching."""
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        docs_no_cache, stats_no_cache = process_uploads_cached(uploads, cache=None)
        assert stats_no_cache.misses == 1

        fresh_doc = process_upload("hssc.txt", INTERMEDIATE_CONTENT)
        assert docs_no_cache[0].field_value("name") == fresh_doc.field_value("name")
        assert docs_no_cache[0].field_value("aggregate") == fresh_doc.field_value("aggregate")


class TestCacheStatsStructure:
    def test_stats_per_document_entries(self) -> None:
        cache = DocumentCache()
        uploads = [
            ("hssc.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", CNIC_CONTENT),
        ]

        _, stats = process_uploads_cached(uploads, cache=cache)

        assert len(stats.per_document) == 2
        for entry in stats.per_document:
            assert "filename" in entry
            assert "cache_hit" in entry
            assert "processing_ms" in entry
            assert entry["cache_hit"] is False
            assert entry["processing_ms"] >= 0

    def test_total_ms_accumulates(self) -> None:
        cache = DocumentCache()
        uploads = [("hssc.txt", INTERMEDIATE_CONTENT)]

        _, stats = process_uploads_cached(uploads, cache=cache)

        assert stats.total_ms >= 0
        per_doc_total = sum(e["processing_ms"] for e in stats.per_document)
        assert stats.total_ms == per_doc_total
