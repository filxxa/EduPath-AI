"""SHA-256 content-hash caching for the document processing pipeline."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from backend.documents.models import ExtractedDocument
from backend.documents.pipeline import process_upload


def fingerprint(content: bytes) -> str:
    """Return the SHA-256 hex digest of *content*."""
    return hashlib.sha256(content).hexdigest()


def _cache_key(content: bytes, user_category: str | None) -> str:
    fp = fingerprint(content)
    if user_category:
        return f"{fp}:{user_category}"
    return fp


@dataclass
class CacheEntry:
    """A cached processing result with timing metadata."""

    document_dict: dict[str, Any]
    processing_ms: float
    cached: bool = False


@dataclass
class CacheStats:
    """Summary of cache hits/misses for a batch run."""

    hits: int = 0
    misses: int = 0
    total_ms: float = 0.0
    per_document: list[dict[str, Any]] = field(default_factory=list)


class DocumentCache:
    """In-memory cache keyed by content fingerprint + user_category.

    Designed to be stored in ``st.session_state`` so it survives reruns.
    """

    def __init__(self, store: dict[str, dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = store if store is not None else {}

    def get(self, content: bytes, user_category: str | None) -> CacheEntry | None:
        key = _cache_key(content, user_category)
        entry = self._store.get(key)
        if entry is None:
            return None
        return CacheEntry(
            document_dict=entry["document_dict"],
            processing_ms=entry["processing_ms"],
            cached=True,
        )

    def put(
        self,
        content: bytes,
        user_category: str | None,
        doc: ExtractedDocument,
        processing_ms: float,
    ) -> None:
        key = _cache_key(content, user_category)
        self._store[key] = {
            "document_dict": doc.to_dict(),
            "processing_ms": processing_ms,
        }

    def invalidate(self, content: bytes, user_category: str | None) -> None:
        key = _cache_key(content, user_category)
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)


def process_uploads_cached(
    uploads: list[tuple[str, bytes]],
    user_categories: dict[str, str] | None = None,
    cache: DocumentCache | None = None,
) -> tuple[list[ExtractedDocument], CacheStats]:
    """Process uploads with content-hash caching.

    Returns the list of ``ExtractedDocument`` results and a ``CacheStats``
    object with per-document timing and hit/miss information.

    Documents whose content bytes match a previously cached fingerprint are
    deserialized from the cache without re-running OCR or extraction.
    """
    categories = user_categories or {}
    results: list[ExtractedDocument] = []
    stats = CacheStats()

    for filename, content in uploads:
        user_cat = categories.get(filename)
        entry = cache.get(content, user_cat) if cache else None

        if entry is not None:
            doc = ExtractedDocument.from_dict(entry.document_dict)
            stats.hits += 1
            rounded_ms = round(entry.processing_ms, 2)
            stats.total_ms += rounded_ms
            stats.per_document.append({
                "filename": filename,
                "cache_hit": True,
                "processing_ms": rounded_ms,
            })
        else:
            t0 = time.perf_counter()
            doc = process_upload(filename, content, user_category=user_cat)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

            if cache is not None:
                cache.put(content, user_cat, doc, elapsed_ms)

            stats.misses += 1
            stats.total_ms += elapsed_ms
            stats.per_document.append({
                "filename": filename,
                "cache_hit": False,
                "processing_ms": elapsed_ms,
            })

        results.append(doc)

    return results, stats
