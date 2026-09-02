"""Document intelligence pipeline public facade."""
from __future__ import annotations

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
    "Conflict",
    "ExtractedDocument",
    "ExtractedField",
    "MergeProposal",
    "ValidationResult",
    "process_upload",
    "process_uploads",
    "process_uploads_and_propose_profile",
    "propose_profile",
]
