from backend.documents.models import ExtractedDocument
from backend.parser import (
    build_profile_from_parsed,
    build_profile_proposal,
    parse_upload,
)


CONTENT = b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4"


def test_parse_upload_preserves_legacy_shape() -> None:
    parsed = parse_upload("hssc_transcript.txt", CONTENT)

    assert parsed["document_type"] == "Academic Transcript (FSc/Intermediate)"
    assert parsed["qualification"] == "FSc Pre-Engineering"
    assert parsed["board"] == "BISE Lahore"
    assert parsed["aggregate"] == 88.4
    assert parsed["name"] == "Ali Hassan"
    assert parsed["validation"]["valid"] is True


def test_build_profile_from_parsed_returns_legacy_profile() -> None:
    parsed = [parse_upload("hssc_transcript.txt", CONTENT)]

    profile = build_profile_from_parsed(parsed)

    assert profile["name"] == "Ali Hassan"
    assert profile["father_name"] is None
    assert profile["qualification"] == "FSc Pre-Engineering"
    assert profile["board"] == "BISE Lahore"
    assert profile["aggregate"] == 88.4
    assert profile["total_marks"] is None
    assert profile["obtained_marks"] is None
    assert profile["roll_number"] is None
    assert profile["hssc_group"] == "Pre-Engineering"
    assert profile["hssc_percentage"] == 88.4
    assert profile["ssc_percentage"] is None
    assert profile["test_scores"] == {}
    assert profile["documents"] == ["Academic Transcript (FSc/Intermediate)"]
    assert "document_records" in profile


def test_build_profile_proposal_preserves_conflicts_and_warnings() -> None:
    parsed = [
        parse_upload("hssc_transcript.txt", CONTENT),
        parse_upload("matric_result.txt", b"Name: Sara Khan\nAggregate: 92.0"),
    ]

    proposal = build_profile_proposal(parsed)

    assert proposal["profile"]["name"] == "Ali Hassan"
    assert proposal["profile"]["aggregate"] == 88.4
    assert {conflict["field"] for conflict in proposal["conflicts"]} == {"name", "aggregate"}
    assert proposal["warnings"]


def test_parser_round_trips_additive_ocr_metadata() -> None:
    parsed = parse_upload("hssc_transcript.txt", CONTENT)
    parsed.update(
        {
            "ocr_confidence": 87.5,
            "page_count": 2,
            "pages_processed": 2,
            "extraction_method": "pdf_ocr",
            "is_scanned_pdf": True,
        }
    )

    round_tripped = ExtractedDocument.from_dict(parsed).to_dict()
    proposal = build_profile_proposal([round_tripped])

    assert proposal["profile"]["name"] == "Ali Hassan"
    assert round_tripped["qualification"] == "FSc Pre-Engineering"
    assert round_tripped["ocr_confidence"] == 87.5
    assert round_tripped["page_count"] == 2
    assert round_tripped["pages_processed"] == 2
    assert round_tripped["is_scanned_pdf"] is True
