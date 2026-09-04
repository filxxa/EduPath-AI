from backend.documents.merging import merge_documents
from backend.documents.models import ExtractedDocument, ExtractedField, ValidationResult


def make_document(
    filename: str,
    document_type: str,
    category: str | None,
    **values: object,
) -> ExtractedDocument:
    fields = [
        ExtractedField(
            field=name,
            value=value,
            confidence=None,
            source_document=filename,
            extraction_method="test",
        )
        for name, value in values.items()
    ]
    return ExtractedDocument(
        filename=filename,
        document_type=document_type,
        canonical_category=category,
        validation=ValidationResult(),
        extraction_method="text",
        raw_text="",
        fields=fields,
    )


def test_merges_one_document_into_a_profile() -> None:
    document = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        name="Ali Hassan",
        qualification="FSc Pre-Engineering",
        board="BISE Lahore",
        aggregate=88.4,
    )

    proposal = merge_documents([document])

    assert proposal.profile["name"] == "Ali Hassan"
    assert proposal.profile["father_name"] is None
    assert proposal.profile["qualification"] == "FSc Pre-Engineering"
    assert proposal.profile["board"] == "BISE Lahore"
    assert proposal.profile["aggregate"] == 88.4
    assert proposal.profile["total_marks"] is None
    assert proposal.profile["obtained_marks"] is None
    assert proposal.profile["roll_number"] is None
    assert proposal.profile["hssc_group"] is None
    assert proposal.profile["hssc_percentage"] is None
    assert proposal.profile["ssc_percentage"] is None
    assert proposal.profile["test_scores"] == {}
    assert proposal.profile["documents"] == ["Academic Transcript (FSc/Intermediate)"]
    assert len(proposal.profile["document_records"]) == 1
    assert proposal.profile["document_records"][0]["category"] == "intermediate_transcript"
    assert proposal.conflicts == []


def test_merges_compatible_documents_without_conflicts() -> None:
    intermediate = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        name="Ali Hassan",
        qualification="FSc",
        board="BISE Lahore",
        aggregate=87.0,
    )
    cnic = make_document(
        "cnic.txt", "CNIC / B-Form", "cnic_bform", name="Ali Hassan"
    )

    proposal = merge_documents([intermediate, cnic])

    assert proposal.profile["name"] == "Ali Hassan"
    assert proposal.conflicts == []
    assert proposal.warnings == []


def test_detects_name_qualification_and_aggregate_conflicts() -> None:
    intermediate = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        name="Ali Hassan",
        qualification="FSc",
        aggregate=82.0,
    )
    matric = make_document(
        "matric.txt",
        "Matriculation Certificate",
        "matric_certificate",
        name="Sara Khan",
        qualification="Matric",
        aggregate=91.0,
    )

    proposal = merge_documents([intermediate, matric])

    assert {conflict.field for conflict in proposal.conflicts} == {
        "name",
        "qualification",
        "aggregate",
    }
    assert proposal.profile["name"] == "Ali Hassan"
    assert proposal.profile["aggregate"] == 82.0
    assert any("Conflicting aggregate values found" in warning for warning in proposal.warnings)


def test_prefers_intermediate_aggregate_over_higher_matric_aggregate() -> None:
    intermediate = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        aggregate=78.0,
    )
    matric = make_document(
        "matric.txt", "Matriculation Certificate", "matric_certificate", aggregate=94.0
    )

    proposal = merge_documents([matric, intermediate])

    assert proposal.profile["aggregate"] == 78.0


def test_keeps_optional_documents_without_creating_conflicts() -> None:
    intermediate = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        aggregate=86.0,
    )
    domicile = make_document("domicile.txt", "Domicile Certificate", "domicile")
    photograph = make_document("photo.txt", "Photograph", "photographs")

    proposal = merge_documents([intermediate, domicile, photograph])

    assert proposal.documents == [
        "Academic Transcript (FSc/Intermediate)",
        "Domicile Certificate",
        "Photograph",
    ]
    assert proposal.conflicts == []


def test_keeps_valid_classified_document_without_extractable_fields() -> None:
    cnic = make_document("cnic.txt", "CNIC / B-Form", "cnic_bform")

    proposal = merge_documents([cnic])

    assert proposal.documents == ["CNIC / B-Form"]
    assert proposal.profile["documents"] == ["CNIC / B-Form"]


def test_excludes_invalid_and_unclassified_documents_from_profile_presence() -> None:
    invalid = make_document("broken.txt", "CNIC / B-Form", "cnic_bform")
    invalid.validation.add_error("Unreadable document")
    unclassified = make_document("supporting.txt", "Supporting Document", None)

    proposal = merge_documents([invalid, unclassified])

    assert proposal.documents == []
    assert proposal.profile["documents"] == []


def test_carries_father_name_through_merge() -> None:
    document = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        name="Ali Hassan",
        father_name="Muhammad Hassan",
    )

    proposal = merge_documents([document])

    assert proposal.profile["father_name"] == "Muhammad Hassan"


def test_carries_roll_number_through_merge() -> None:
    document = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        roll_number="789012",
    )

    proposal = merge_documents([document])

    assert proposal.profile["roll_number"] == "789012"


def test_carries_hssc_group_through_merge() -> None:
    document = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        hssc_group="Pre-Engineering",
    )

    proposal = merge_documents([document])

    assert proposal.profile["hssc_group"] == "Pre-Engineering"


def test_carries_total_and_obtained_marks_through_merge() -> None:
    document = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        total_marks=700,
        obtained_marks=535,
    )

    proposal = merge_documents([document])

    assert proposal.profile["total_marks"] == 700
    assert proposal.profile["obtained_marks"] == 535


def test_prefers_intermediate_transcript_for_identity_fields() -> None:
    intermediate = make_document(
        "hssc.txt",
        "Academic Transcript (FSc/Intermediate)",
        "intermediate_transcript",
        father_name="Intermediate Father",
        roll_number="111222",
        hssc_group="Pre-Medical",
    )
    matric = make_document(
        "matric.txt",
        "Matriculation Certificate",
        "matric_certificate",
        father_name="Matric Father",
        roll_number="999888",
        hssc_group="General Science",
    )

    proposal = merge_documents([matric, intermediate])

    assert proposal.profile["father_name"] == "Intermediate Father"
    assert proposal.profile["roll_number"] == "111222"
    assert proposal.profile["hssc_group"] == "Pre-Medical"


def make_document_with_user_category(
    filename: str,
    document_type: str,
    canonical_category: str | None,
    user_category: str | None,
    **values: object,
) -> ExtractedDocument:
    fields = [
        ExtractedField(
            field=name,
            value=value,
            confidence=None,
            source_document=filename,
            extraction_method="test",
        )
        for name, value in values.items()
    ]
    return ExtractedDocument(
        filename=filename,
        document_type=document_type,
        canonical_category=canonical_category,
        user_category=user_category,
        validation=ValidationResult(),
        extraction_method="text",
        raw_text="some text",
        fields=fields,
    )


class TestDocumentRecords:
    def test_merge_produces_document_records(self):
        doc = make_document(
            "hssc.txt",
            "Academic Transcript (FSc/Intermediate)",
            "intermediate_transcript",
            name="Ali Hassan",
            aggregate=88.0,
        )
        proposal = merge_documents([doc])
        records = proposal.profile.get("document_records", [])
        assert len(records) == 1
        assert records[0]["filename"] == "hssc.txt"
        assert records[0]["category"] == "intermediate_transcript"
        assert records[0]["extraction_status"] == "extracted"

    def test_document_records_uses_effective_category(self):
        doc = make_document_with_user_category(
            "scan.pdf",
            "Other Document",
            "intermediate_transcript",
            user_category="other",
            name="Test",
        )
        proposal = merge_documents([doc])
        records = proposal.profile["document_records"]
        assert records[0]["category"] == "other"

    def test_document_records_failed_extraction(self):
        doc = ExtractedDocument(
            filename="broken.pdf",
            document_type="Unknown",
            canonical_category=None,
            validation=ValidationResult(),
            extraction_method="error",
            raw_text="",
            fields=[],
        )
        proposal = merge_documents([doc])
        records = proposal.profile["document_records"]
        assert records[0]["extraction_status"] == "failed"

    def test_document_records_partial_extraction(self):
        doc = ExtractedDocument(
            filename="scan.pdf",
            document_type="Transcript",
            canonical_category="intermediate_transcript",
            validation=ValidationResult(),
            extraction_method="image_ocr",
            raw_text="Name: Ali",
            fields=[],
        )
        proposal = merge_documents([doc])
        records = proposal.profile["document_records"]
        assert records[0]["extraction_status"] == "partial"

    def test_multi_doc_categories_accumulate(self):
        doc1 = make_document_with_user_category(
            "test1.pdf", "Entry Test", "entry_test_score", "entry_test_score",
        )
        doc2 = make_document_with_user_category(
            "test2.pdf", "Entry Test", "entry_test_score", "entry_test_score",
        )
        proposal = merge_documents([doc1, doc2])
        records = proposal.profile["document_records"]
        entry_records = [r for r in records if r["category"] == "entry_test_score"]
        assert len(entry_records) == 2

    def test_legacy_documents_list_still_populated(self):
        doc = make_document(
            "hssc.txt",
            "Academic Transcript (FSc/Intermediate)",
            "intermediate_transcript",
            aggregate=88.0,
        )
        proposal = merge_documents([doc])
        assert "documents" in proposal.profile
        assert len(proposal.profile["documents"]) > 0
