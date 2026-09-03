"""Typed models for the document intelligence pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Outcome of file validation."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


@dataclass
class ExtractedField:
    """A single structured field extracted from a document."""

    field: str
    value: Any
    confidence: float | None
    source_document: str
    extraction_method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence,
            "source_document": self.source_document,
            "extraction_method": self.extraction_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedField:
        return cls(
            field=data["field"],
            value=data["value"],
            confidence=data.get("confidence"),
            source_document=data.get("source_document", ""),
            extraction_method=data.get("extraction_method", ""),
        )


@dataclass
class ExtractedDocument:
    """Result of parsing a single uploaded document."""

    filename: str
    document_type: str
    canonical_category: str | None
    validation: ValidationResult
    extraction_method: str
    raw_text: str
    fields: list[ExtractedField]
    ocr_note: str | None = None
    is_scanned_pdf: bool | None = None
    ocr_confidence: float | None = None
    page_count: int | None = None
    pages_processed: int | None = None
    ocr_attempts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict that preserves the legacy parser contract."""
        legacy_fields = {
            "qualification": None,
            "board": None,
            "aggregate": None,
            "hssc_percentage": None,
            "ssc_percentage": None,
            "hssc_group": None,
            "name": None,
            "test_score": None,
        }
        for extracted_field in self.fields:
            if extracted_field.field in legacy_fields and extracted_field.value is not None:
                legacy_fields[extracted_field.field] = extracted_field.value

        return {
            "filename": self.filename,
            "document_type": self.document_type,
            "canonical_category": self.canonical_category,
            "validation": {
                "valid": self.validation.valid,
                "errors": self.validation.errors,
                "warnings": self.validation.warnings,
            },
            "extraction_method": self.extraction_method,
            "raw_text": self.raw_text,
            "fields": [extracted_field.to_dict() for extracted_field in self.fields],
            "ocr_note": self.ocr_note,
            "is_scanned_pdf": self.is_scanned_pdf,
            "ocr_confidence": self.ocr_confidence,
            "page_count": self.page_count,
            "pages_processed": self.pages_processed,
            "ocr_attempts": self.ocr_attempts,
            **legacy_fields,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractedDocument:
        validation = data.get("validation", {})
        return cls(
            filename=data.get("filename", ""),
            document_type=data.get("document_type", "Supporting Document"),
            canonical_category=data.get("canonical_category"),
            validation=ValidationResult(
                valid=validation.get("valid", True),
                errors=validation.get("errors", []),
                warnings=validation.get("warnings", []),
            ),
            extraction_method=data.get("extraction_method", "unknown"),
            raw_text=data.get("raw_text", ""),
            fields=[ExtractedField.from_dict(item) for item in data.get("fields", [])],
            ocr_note=data.get("ocr_note"),
            is_scanned_pdf=data.get("is_scanned_pdf"),
            ocr_confidence=data.get("ocr_confidence"),
            page_count=data.get("page_count"),
            pages_processed=data.get("pages_processed"),
            ocr_attempts=data.get("ocr_attempts", []),
        )

    def field_value(self, name: str) -> Any:
        """Return the first extracted value for a field, if any."""
        for extracted_field in self.fields:
            if extracted_field.field == name:
                return extracted_field.value
        return None


@dataclass
class Conflict:
    """A disagreement between two or more document extractions."""

    field: str
    values: list[Any] = field(default_factory=list)
    source_documents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "values": self.values,
            "source_documents": self.source_documents,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conflict:
        return cls(
            field=data["field"],
            values=data.get("values", []),
            source_documents=data.get("source_documents", []),
        )


@dataclass
class MergeProposal:
    """Proposed profile built from multiple documents, plus conflicts/warnings."""

    profile: dict[str, Any]
    documents: list[str] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "documents": self.documents,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeProposal:
        return cls(
            profile=data.get("profile", {}),
            documents=data.get("documents", []),
            conflicts=[Conflict.from_dict(item) for item in data.get("conflicts", [])],
            warnings=data.get("warnings", []),
        )
