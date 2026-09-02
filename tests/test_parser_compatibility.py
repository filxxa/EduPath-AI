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

    assert profile == {
        "name": "Ali Hassan",
        "qualification": "FSc Pre-Engineering",
        "board": "BISE Lahore",
        "aggregate": 88.4,
        "documents": ["Academic Transcript (FSc/Intermediate)"],
    }


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
