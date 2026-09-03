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

    assert proposal.profile == {
        "name": "Ali Hassan",
        "father_name": None,
        "qualification": "FSc Pre-Engineering",
        "board": "BISE Lahore",
        "aggregate": 88.4,
        "total_marks": None,
        "obtained_marks": None,
        "roll_number": None,
        "hssc_group": None,
        "hssc_percentage": None,
        "ssc_percentage": None,
        "test_scores": {},
        "documents": ["Academic Transcript (FSc/Intermediate)"],
    }
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
