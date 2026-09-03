"""Tests for the RAG advisor pipeline.

These tests do not require a Groq API key — the LLM is stubbed where needed.
ChromaDB is used through an ephemeral in-memory client, so no .rag_cache/
artifacts are written to disk.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.rag import config
from backend.rag import indexer as indexer_mod
from backend.rag import llm as llm_mod
from backend.rag import prompter, retriever as retriever_mod
import backend.rag as rag_pkg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_universities(tmp_path: Path) -> Path:
    """A minimal universities.json with one university and one program."""
    data = {
        "metadata": {"version": "test", "last_updated": "2026-01-01"},
        "universities": [
            {
                "id": "testuni",
                "name": "Test University",
                "full_name": "Test University of Pakistan",
                "location": "Islamabad",
                "website": "https://testuni.example",
                "description": "A test university.",
                "sources": [
                    {"url": "https://testuni.example/policy", "last_verified": "2026-01-01"}
                ],
                "programs": [
                    {
                        "id": "bs-cs",
                        "name": "BS Computer Science",
                        "duration": "4 years",
                        "requirements": {
                            "qualification": ["FSc Pre-Engineering", "ICS"],
                            "minimum_aggregate": 60.0,
                            "estimated_cutoff": 75.0,
                            "aggregate_formula": "(matric*0.2 + inter*0.5 + test*0.3)",
                            "admission_test": "NTS-NAT IE/ICS",
                            "required_documents": [
                                {"name": "Matric certificate", "required": True},
                                {"name": "CNIC B Form", "required": True},
                            ],
                            "application_deadline": "2026-12-31",
                            "fee_estimate_pkr": 450000,
                            "notes": "Merit scholarships available for top scorers.",
                        },
                    }
                ],
            }
        ],
    }
    path = tmp_path / "universities.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def synthesized_policies(tmp_path: Path, tiny_universities: Path) -> Path:
    policies_dir = tmp_path / "policies"
    from backend.rag.policy_synthesis import synthesize_policy_files

    synthesize_policy_files(tiny_universities, policies_dir)
    return policies_dir


# ---------------------------------------------------------------------------
# Policy synthesis
# ---------------------------------------------------------------------------


class TestPolicySynthesis:
    def test_deterministic_output(self, tmp_path: Path, tiny_universities: Path) -> None:
        from backend.rag.policy_synthesis import synthesize_policy_files

        out_a = tmp_path / "a"
        out_b = tmp_path / "b"
        manifest_a = synthesize_policy_files(tiny_universities, out_a)
        manifest_b = synthesize_policy_files(tiny_universities, out_b)

        files_a = sorted((out_a / "testuni").glob("*.txt"))
        files_b = sorted((out_b / "testuni").glob("*.txt"))
        assert len(files_a) == len(files_b)
        for fa, fb in zip(files_a, files_b):
            assert fa.read_text(encoding="utf-8") == fb.read_text(encoding="utf-8")

    def test_program_file_contains_sections(self, synthesized_policies: Path) -> None:
        program_file = synthesized_policies / "testuni" / "bs-cs.txt"
        assert program_file.exists()
        text = program_file.read_text(encoding="utf-8")
        for section in ("Eligibility", "Aggregate", "Admission Test", "Required Documents", "Deadline", "Fees"):
            assert f"## {section}" in text

    def test_overview_file_written(self, synthesized_policies: Path) -> None:
        overview = synthesized_policies / "testuni" / "overview.txt"
        assert overview.exists()
        assert "Test University" in overview.read_text(encoding="utf-8")

    def test_manifest_written(self, synthesized_policies: Path) -> None:
        manifest = synthesized_policies / "MANIFEST.md"
        assert manifest.exists()
        assert "Policy Corpus Manifest" in manifest.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Indexer: section splitting and metadata
# ---------------------------------------------------------------------------


class TestIndexer:
    def test_split_respects_section_boundaries(self) -> None:
        text = (
            "# Uni — Program\n\n"
            "Preamble text that is long enough to pass the minimum threshold.\n\n"
            "## Eligibility\n\n"
            "Accepted qualifications for this program include FSc Pre-Engineering "
            "and ICS with at least sixty percent aggregate overall.\n\n"
            "## Deadline\n\n"
            "The application deadline for the fall 2026 intake is 2026-12-31 and "
            "late submissions will not be entertained under any circumstance.\n"
        )
        chunks = indexer_mod._split_sections(
            text=text,
            university_id="u",
            university_name="Uni",
            program_id="p",
            program_name="Program",
            source_file="p.txt",
        )
        categories = [c.category for c in chunks]
        assert "eligibility" in categories
        assert "deadline" in categories
        eligibility_chunk = next(c for c in chunks if c.category == "eligibility")
        assert "Deadline" not in eligibility_chunk.text
        deadline_chunk = next(c for c in chunks if c.category == "deadline")
        assert "Eligibility" not in deadline_chunk.text

    def test_split_drops_short_chunks(self) -> None:
        text = "# H\n\n## Eligibility\n\nToo short.\n"
        chunks = indexer_mod._split_sections(
            text=text,
            university_id="u",
            university_name="Uni",
            program_id="p",
            program_name="Program",
            source_file="p.txt",
        )
        assert chunks == []

    def test_doc_id_is_deterministic(self) -> None:
        a = indexer_mod.PolicyChunk("u", "Uni", "p", "Prog", "eligibility", "f.txt", "hello")
        b = indexer_mod.PolicyChunk("u", "Uni", "p", "Prog", "eligibility", "f.txt", "hello")
        assert indexer_mod._doc_id(a) == indexer_mod._doc_id(b)

    def test_doc_id_differs_by_text(self) -> None:
        a = indexer_mod.PolicyChunk("u", "Uni", "p", "Prog", "eligibility", "f.txt", "hello")
        b = indexer_mod.PolicyChunk("u", "Uni", "p", "Prog", "eligibility", "f.txt", "world")
        assert indexer_mod._doc_id(a) != indexer_mod._doc_id(b)


# ---------------------------------------------------------------------------
# Retriever: intent detection
# ---------------------------------------------------------------------------


class TestIntentDetection:
    def test_detects_university_by_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            retriever_mod,
            "_load_alias_table",
            lambda: {"testuni": "testuni", "test university": "testuni"},
        )
        monkeypatch.setattr(
            retriever_mod,
            "load_universities",
            lambda: {"universities": [{"id": "testuni", "name": "Test University"}]},
        )
        intent = retriever_mod.detect_intent("What are the fees at testuni?")
        assert intent["university_id"] == "testuni"

    def test_detects_university_by_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            retriever_mod,
            "_load_alias_table",
            lambda: {"test university": "testuni"},
        )
        monkeypatch.setattr(
            retriever_mod,
            "load_universities",
            lambda: {"universities": [{"id": "testuni", "name": "Test University"}]},
        )
        intent = retriever_mod.detect_intent("Tell me about Test University")
        assert intent["university_id"] == "testuni"

    def test_detects_category(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(retriever_mod, "_load_alias_table", lambda: {})
        intent = retriever_mod.detect_intent("When is the deadline?")
        assert intent["category"] == "deadline"

    def test_no_university_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(retriever_mod, "_load_alias_table", lambda: {})
        intent = retriever_mod.detect_intent("How should I prepare?")
        assert intent["university_id"] is None


# ---------------------------------------------------------------------------
# Prompter: profile pruning and prompt construction
# ---------------------------------------------------------------------------


class TestPrompter:
    def test_prune_returns_academic_by_default(self) -> None:
        profile = {
            "name": "Ali",
            "qualification": "FSc",
            "aggregate": 80.0,
            "documents": ["CNIC"],
            "test_scores": {"NAT": 75},
        }
        pruned = prompter.prune_profile(profile, "Tell me about LUMS")
        assert "name" in pruned
        assert "qualification" in pruned
        assert "documents" not in pruned
        assert "test_scores" not in pruned

    def test_prune_keeps_documents_when_asked(self) -> None:
        profile = {"name": "Ali", "documents": ["CNIC"], "aggregate": 80.0}
        pruned = prompter.prune_profile(profile, "What documents do I still need?")
        assert "documents" in pruned

    def test_prune_keeps_test_when_asked(self) -> None:
        profile = {"name": "Ali", "test_scores": {"NAT": 75}, "aggregate": 80.0}
        pruned = prompter.prune_profile(profile, "How do I register for the entry test?")
        assert "test_scores" in pruned

    def test_prune_handles_empty_profile(self) -> None:
        assert prompter.prune_profile({}, "any question") == {}

    def test_bundle_contains_evidence(self) -> None:
        chunk = retriever_mod.RetrievedChunk(
            text="Deadline is 2026-12-31.",
            university_id="u",
            university_name="Uni",
            program_id="p",
            program_name="Prog",
            category="deadline",
            source_file="f.txt",
            distance=0.1,
        )
        bundle = prompter.build_prompt("When is the deadline?", [chunk])
        assert "2026-12-31" in bundle.user_message
        assert "grounded" in bundle.system.lower() or "evidence" in bundle.system.lower()

    def test_bundle_no_evidence_uses_placeholder(self) -> None:
        bundle = prompter.build_prompt("Anything?", [])
        assert "No relevant policy passages" in bundle.user_message


# ---------------------------------------------------------------------------
# LLM: graceful failure when key is missing
# ---------------------------------------------------------------------------


class TestLlmClient:
    def test_generate_returns_error_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_mod, "_get_api_key", lambda: None)
        bundle = prompter.PromptBundle(system="S", user_message="U")
        response = llm_mod.generate(bundle)
        assert response.error is not None
        assert "API key" in response.error
        assert response.answer == ""

    def test_is_available_false_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(llm_mod, "_get_api_key", lambda: None)
        assert llm_mod.is_available() is False

    def test_package_status_reports_missing_or_incompatible_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unavailable_import() -> tuple[object, ...]:
            raise ImportError("No module named 'groq'")

        monkeypatch.setattr(llm_mod, "_import_groq_symbols", unavailable_import)
        status = llm_mod.get_package_status()
        response = llm_mod.generate(prompter.PromptBundle(system="S", user_message="U"))

        assert status.available is False
        assert status.interpreter == llm_mod.sys.executable
        assert status.message is not None and "missing or incompatible" in status.message
        assert response.error is not None and "missing or incompatible" in response.error

    def test_available_package_without_key_reports_key_status(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        available_symbols = (object, Exception, Exception, Exception, Exception, Exception, Exception)
        monkeypatch.setattr(llm_mod, "_import_groq_symbols", lambda: available_symbols)
        monkeypatch.setattr(llm_mod, "_get_api_key", lambda: None)

        status = llm_mod.get_package_status()
        response = llm_mod.generate(prompter.PromptBundle(system="S", user_message="U"))

        assert status.available is True
        assert llm_mod.is_available() is False
        assert response.error is not None and "API key is not configured" in response.error


# ---------------------------------------------------------------------------
# End-to-end: ask() with stubbed LLM and ephemeral ChromaDB
# ---------------------------------------------------------------------------


class TestAskEndToEnd:
    def _build_collection(self, synthesized_policies: Path):
        import chromadb
        import uuid

        client = chromadb.Client()
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        ef = SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
        unique_name = f"{config.COLLECTION_NAME}_{uuid.uuid4().hex[:8]}"
        collection = client.create_collection(
            name=unique_name,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        indexer_mod.index_policies(policies_dir=synthesized_policies, collection=collection)
        return collection

    def test_ask_falls_back_without_groq_key(
        self, monkeypatch: pytest.MonkeyPatch, synthesized_policies: Path
    ) -> None:
        monkeypatch.setattr(llm_mod, "_get_api_key", lambda: None)
        collection = self._build_collection(synthesized_policies)

        ret = retriever_mod.Retriever(collection)
        monkeypatch.setattr(retriever_mod, "get_retriever", lambda collection=None: ret)

        profile = {
            "name": "Ali",
            "qualification": "FSc Pre-Engineering",
            "aggregate": 80.0,
            "target_university": "testuni",
            "target_program": "bs-cs",
        }
        eligibility = {
            "verdict": "ELIGIBLE",
            "eligible": True,
            "conditional": False,
            "reasons": ["Qualification accepted.", "Aggregate 80% meets 60%."],
            "missing_documents": [],
            "admission_test": "NTS-NAT IE/ICS",
            "test_missing": False,
            "application_deadline": "2026-12-31",
            "days_remaining": 120,
            "estimated_cutoff": 75.0,
            "minimum_aggregate": 60.0,
        }

        monkeypatch.setattr(
            rag_pkg,
            "_rule_based_fallback",
            lambda question, profile, eligibility: f"Rule-based reply for: {question}",
        )

        result = rag_pkg.ask(
            question="What is the deadline?",
            profile=profile,
            eligibility=eligibility,
        )

        assert result.engine == "rule-based"
        assert "Rule-based reply" in result.answer
        assert result.error is None

    def test_retrieval_filters_by_university(
        self, monkeypatch: pytest.MonkeyPatch, synthesized_policies: Path
    ) -> None:
        collection = self._build_collection(synthesized_policies)
        ret = retriever_mod.Retriever(collection)
        chunks = ret.retrieve("What are the eligibility requirements at Test University?")
        assert all(c.university_id == "testuni" for c in chunks)
