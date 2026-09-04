"""Document intelligence pipeline public facade."""
from __future__ import annotations

from backend.documents.cache import (
    CacheStats,
    DocumentCache,
    fingerprint,
    process_uploads_cached,
)
from backend.documents.models import (
    Conflict,
    ExtractedDocument,
    ExtractedField,
    MergeProposal,
    ValidationResult,
)
from backend.documents.pipeline import (
    process_upload,
    process_uploads,
    process_uploads_and_propose_profile,
    propose_profile,
)

__all__ = [
    "CacheStats",
    "Conflict",
    "DocumentCache",
    "ExtractedDocument",
    "ExtractedField",
    "MergeProposal",
    "ValidationResult",
    "fingerprint",
    "process_upload",
    "process_uploads",
    "process_uploads_and_propose_profile",
    "process_uploads_cached",
    "propose_profile",
]
