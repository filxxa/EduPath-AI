from backend.documents.pipeline import (
    process_upload,
    process_uploads,
    process_uploads_and_propose_profile,
)


INTERMEDIATE_CONTENT = (
    b"Name: Ali Hassan\nFSc Pre-Engineering\nBISE Lahore\nAggregate: 88.4\nNAT Score: 89"
)


def test_process_upload_runs_document_pipeline() -> None:
    document = process_upload("hssc_transcript.txt", INTERMEDIATE_CONTENT)

    assert document.validation.valid
    assert document.canonical_category == "intermediate_transcript"
    assert document.extraction_method == "text"
    assert document.field_value("name") == "Ali Hassan"
    assert document.field_value("qualification") == "FSc Pre-Engineering"
    assert document.field_value("aggregate") == 88.4


def test_invalid_upload_short_circuits_pipeline() -> None:
    document = process_upload("transcript.docx", b"content")

    assert not document.validation.valid
    assert document.document_type == "Unsupported / Invalid File"
    assert document.extraction_method == "none"
    assert document.fields == []


def test_process_uploads_handles_multiple_files() -> None:
    documents = process_uploads(
        [
            ("hssc_transcript.txt", INTERMEDIATE_CONTENT),
            ("cnic.txt", b"Name: Ali Hassan\nCNIC 12345"),
        ]
    )

    assert [document.canonical_category for document in documents] == [
        "intermediate_transcript",
        "cnic_bform",
    ]


def test_processes_uploads_and_builds_profile_proposal() -> None:
    documents, proposal = process_uploads_and_propose_profile(
        [
            ("hssc_transcript.txt", INTERMEDIATE_CONTENT),
            (
                "matric_result.txt",
                b"Name: Ali Hassan\nBISE Lahore\nAggregate: 92.0",
            ),
        ]
    )

    assert len(documents) == 2
    assert proposal.profile["name"] == "Ali Hassan"
    assert proposal.profile["aggregate"] == 88.4
