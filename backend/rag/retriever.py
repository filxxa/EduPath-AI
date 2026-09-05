"""University-aware policy retrieval.

If the question mentions a known university, filter retrieval to that
university's chunks first; broaden only if too few results come back.
If the question signals a policy category, bias toward that category.
"""
from __future__ import annotations

from dataclasses import dataclass
import functools
import logging
import re
from typing import Any

from backend.data_loader import load_universities
from backend.rag.config import (
    CATEGORY_KEYWORDS,
    COLLECTION_NAME,
    DEFAULT_K,
    MIN_UNIVERSITY_RESULTS,
    UNIVERSITY_ALIASES,
)
from backend.rag.indexer import build_collection, get_persistent_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    university_id: str
    university_name: str
    program_id: str
    program_name: str
    category: str
    source_file: str
    distance: float

    @property
    def source_label(self) -> str:
        if self.program_id == "overview":
            return f"{self.university_name} (overview)"
        return f"{self.university_name} — {self.program_name}, {self.category}"


@functools.lru_cache(maxsize=1)
def _load_alias_table() -> dict[str, str]:
    """Build alias -> canonical university_id mapping. Cached for the process lifetime.

    Merges explicit aliases from config.UNIVERSITY_ALIASES with aliases derived
    from the university dataset (id, name, full_name). Explicit aliases win on
    conflict so "fast" always resolves to fast-nuces even if another university
    has a similar name.
    """
    merged: dict[str, str] = {}
    try:
        data = load_universities()
    except Exception:
        data = {"universities": []}

    for uni in data.get("universities", []) or []:
        uid = uni.get("id", "")
        if not uid:
            continue
        for raw in (uni.get("id"), uni.get("name"), uni.get("full_name")):
            if raw:
                merged.setdefault(raw.strip().lower(), uid)

    for uid, aliases in UNIVERSITY_ALIASES.items():
        for alias in aliases:
            merged[alias.strip().lower()] = uid

    return merged


def detect_intent(question: str) -> dict[str, Any]:
    q = question.lower()
    aliases = _load_alias_table()

    detected_id: str | None = None
    detected_name: str | None = None
    # Prefer longer alias matches first so "fast-nuces" beats the common word "fast"
    # when both could match in a compound phrase.
    for alias in sorted(aliases.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", q):
            detected_id = aliases[alias]
            break

    if detected_id is not None:
        # Resolve canonical display name from the dataset when possible.
        try:
            data = load_universities()
            for uni in data.get("universities", []) or []:
                if uni.get("id") == detected_id:
                    detected_name = uni.get("name", detected_id)
                    break
        except Exception:
            detected_name = detected_id
        if detected_name is None:
            detected_name = detected_id

    detected_category: str | None = None
    best_hits = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in q)
        if hits > best_hits:
            best_hits = hits
            detected_category = category

    return {
        "university_id": detected_id,
        "university_name": detected_name,
        "category": detected_category,
    }


class Retriever:
    """Wraps a ChromaDB collection for university/category-filtered retrieval."""

    def __init__(self, collection: Any) -> None:
        self._collection = collection

    def retrieve(
        self,
        question: str,
        k: int = DEFAULT_K,
        university_id: str | None = None,
    ) -> list[RetrievedChunk]:
        """Return up to ``k`` chunks relevant to ``question``.

        When ``university_id`` is supplied, it takes precedence over any
        university detected from the question text — this lets the advisor
        page pass the student's session-state selection and avoid cross-
        university noise on generic questions like "When is the deadline?".
        """
        intent = detect_intent(question)
        effective_uni = university_id or intent["university_id"]
        results: list[RetrievedChunk] = []

        if effective_uni:
            try:
                hits = self._collection.query(
                    query_texts=[question],
                    n_results=k,
                    where={"university_id": effective_uni},
                )
                results.extend(_materialize(hits))
            except Exception as exc:
                logger.warning("University-scoped retrieval failed: %s", exc)
                results = []

        if len(results) < MIN_UNIVERSITY_RESULTS:
            try:
                broad = self._collection.query(query_texts=[question], n_results=k)
                seen = {(r.university_id, r.program_id, r.category) for r in results}
                for chunk in _materialize(broad):
                    key = (chunk.university_id, chunk.program_id, chunk.category)
                    if key not in seen:
                        results.append(chunk)
                        seen.add(key)
            except Exception as exc:
                logger.error("Broad retrieval fallback failed: %s", exc)

        if intent["category"] and len(results) > 1:
            results.sort(
                key=lambda c: (0 if c.category == intent["category"] else 1, c.distance)
            )

        return results[:k]


def _materialize(hits: dict[str, Any]) -> list[RetrievedChunk]:
    ids = hits.get("ids", [[]])[0]
    documents = hits.get("documents", [[]])[0]
    metadatas = hits.get("metadatas", [[]])[0]
    distances = hits.get("distances", [[]])[0] if hits.get("distances") else [0.0] * len(ids)
    out: list[RetrievedChunk] = []
    for i, doc_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        out.append(
            RetrievedChunk(
                text=documents[i] if i < len(documents) else "",
                university_id=meta.get("university_id", ""),
                university_name=meta.get("university_name", ""),
                program_id=meta.get("program_id", ""),
                program_name=meta.get("program_name", ""),
                category=meta.get("category", ""),
                source_file=meta.get("source_file", ""),
                distance=float(distances[i]) if i < len(distances) else 0.0,
            )
        )
    return out


def get_retriever(collection: Any | None = None) -> Retriever:
    if collection is None:
        collection = build_collection(get_persistent_client())
    return Retriever(collection)


def retrieve(
    question: str,
    k: int = DEFAULT_K,
    university_id: str | None = None,
) -> list[RetrievedChunk]:
    return get_retriever().retrieve(question, k=k, university_id=university_id)
