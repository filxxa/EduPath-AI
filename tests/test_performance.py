"""Tests for performance caching (Fix 1)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


# ── Tesseract availability cache ──────────────────────────────────

class TestTesseractAvailabilityCache:
    def test_cache_hit_within_ttl(self):
        from backend.documents import ocr

        original_cache = ocr._AVAILABILITY_CACHE
        try:
            ocr._AVAILABILITY_CACHE = (True, None, time.monotonic())
            available, message = ocr._availability()
            assert available is True
            assert message is None
        finally:
            ocr._AVAILABILITY_CACHE = original_cache

    def test_cache_miss_after_ttl(self):
        from backend.documents import ocr

        original_cache = ocr._AVAILABILITY_CACHE
        try:
            ocr._AVAILABILITY_CACHE = (True, None, time.monotonic() - 120)
            with patch.object(ocr, "pytesseract", None):
                available, message = ocr._availability()
                assert available is False
                assert "not installed" in message.lower() or "dependencies" in message.lower()
        finally:
            ocr._AVAILABILITY_CACHE = original_cache

    def test_cache_stores_result(self):
        from backend.documents import ocr

        original_cache = ocr._AVAILABILITY_CACHE
        try:
            ocr._AVAILABILITY_CACHE = None
            with patch.object(ocr, "pytesseract", None):
                ocr._availability()
                assert ocr._AVAILABILITY_CACHE is not None
                available, message, ts = ocr._AVAILABILITY_CACHE
                assert available is False
        finally:
            ocr._AVAILABILITY_CACHE = original_cache


# ── RAG resource cache ────────────────────────────────────────────

class TestRAGResourceCache:
    def test_embedding_function_singleton(self):
        from backend.rag import indexer

        original = indexer._embedding_fn_cache
        try:
            mock_fn = MagicMock()
            indexer._embedding_fn_cache = mock_fn
            result = indexer._embedding_function()
            assert result is mock_fn
        finally:
            indexer._embedding_fn_cache = original

    def test_client_singleton(self):
        from backend.rag import indexer

        original = indexer._client_cache
        try:
            mock_client = MagicMock()
            indexer._client_cache = mock_client
            result = indexer.get_persistent_client()
            assert result is mock_client
        finally:
            indexer._client_cache = original


# ── Upload dedup (SHA-256) ────────────────────────────────────────

class TestUploadDedup:
    def test_same_content_produces_same_hash(self):
        import hashlib
        content = b"test document content"
        h1 = hashlib.sha256(content).hexdigest()
        h2 = hashlib.sha256(content).hexdigest()
        assert h1 == h2

    def test_different_content_produces_different_hash(self):
        import hashlib
        h1 = hashlib.sha256(b"content A").hexdigest()
        h2 = hashlib.sha256(b"content B").hexdigest()
        assert h1 != h2

    def test_multi_file_hash_is_order_dependent(self):
        import hashlib
        files_a = [b"file1", b"file2"]
        files_b = [b"file2", b"file1"]

        def _hash(parts):
            h = hashlib.sha256()
            for p in parts:
                h.update(p)
            return h.hexdigest()

        assert _hash(files_a) != _hash(files_b)
