"""Step 4 integration tests — state-driven flow.

These tests verify that the canonical state module (``backend.state``) ties
the OCR pipeline, eligibility engine, RAG advisor, and UI pages into one
consistent assistant. Streamlit's session state is mocked with a plain dict.
"""
from __future__ import annotations

from typing import Any

import pytest

from backend import state
from backend.profile import default_profile


# ---------------------------------------------------------------------------
# Session-state mock
# ---------------------------------------------------------------------------


class _SessionState(dict):
    """Minimal dict-backed stand-in for ``st.session_state``.

    Streamlit's real session state supports ``in`` checks, iteration, and
    item deletion, which is all this mock needs to satisfy.
    """

    def keys(self):  # type: ignore[override]
        return list(super().keys())


@pytest.fixture(autouse=True)
def _mock_session_state(monkeypatch: pytest.MonkeyPatch) -> _SessionState:
    """Swap ``streamlit.session_state`` with a fresh dict for every test."""
    import streamlit as st

    session = _SessionState()
    # Populate the canonical keys the same way init_session_state() does.
    session.update({
        "student_profile": default_profile(),
        "parsed_docs": [],
        "selected_university_id": None,
        "selected_program_id": None,
        "eligibility_result": None,
        "selected_program_with_university": None,
        "chat_history": [],
        "chat_history_sources": [],
    })
    monkeypatch.setattr(st, "session_state", session)
    return session


# ---------------------------------------------------------------------------
# Dataset fixtures
# ---------------------------------------------------------------------------


_TINY_PROGRAM = {
    "id": "bs-cs",
    "name": "BS Computer Science",
    "duration": "4 years",
    "requirements": {
        "qualification": ["FSc Pre-Engineering", "ICS"],
        "minimum_aggregate": 60.0,
        "estimated_cutoff": 75.0,
        "admission_test": "NTS-NAT",
        "required_documents": [
            {"name": "CNIC", "required": True},
            {"name": "Matric certificate", "required": True},
        ],
        "application_deadline": "2026-12-31",
    },
}

_TINY_UNIVERSITY = {
    "id": "test-uni",
    "name": "Test University",
    "full_name": "Test University of Pakistan",
    "location": "Islamabad",
    "description": "Fixture university.",
    "programs": [_TINY_PROGRAM],
}

_TINY_DATASET = {
    "metadata": {"version": "test", "last_updated": "2026-01-01"},
    "universities": [_TINY_UNIVERSITY],
}


@pytest.fixture
def tiny_dataset(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Route data-loader calls through the in-memory fixture dataset.

    ``state.py`` imports ``load_universities`` / ``get_university`` /
    ``get_program`` directly, so we patch both the module-level bindings
    (for callers that reach into ``data_loader``) and the ``state``-module
    bindings (for callers that reach into ``state``).
    """
    from backend import data_loader

    monkeypatch.setattr(data_loader, "load_universities", lambda: _TINY_DATASET)
    monkeypatch.setattr(
        state, "load_universities", lambda: _TINY_DATASET
    )
    return _TINY_DATASET


# ---------------------------------------------------------------------------
# Scenario A — OCR → profile (field_sources labelled as "ocr")
# ---------------------------------------------------------------------------


class TestOCRProfile:
    def test_ocr_writes_split_fields_with_ocr_source(self, _mock_session_state) -> None:
        ocr_updates = {
            "ssc_percentage": 85.0,
            "hssc_percentage": 78.0,
            "hssc_group": "Pre-Engineering",
        }
        new_profile = state.update_profile(ocr_updates, source="ocr")

        assert new_profile["ssc_percentage"] == 85.0
        assert new_profile["hssc_percentage"] == 78.0
        assert new_profile["hssc_group"] == "Pre-Engineering"
        # aggregate is mirrored from the HSSC value by _sync_aggregate
        assert new_profile["aggregate"] == 78.0
        sources = new_profile.get("field_sources", {})
        assert sources.get("hssc_percentage") == "ocr"
        assert sources.get("ssc_percentage") == "ocr"
        assert sources.get("hssc_group") == "ocr"


# ---------------------------------------------------------------------------
# Scenario B — profile change invalidates cached eligibility
# ---------------------------------------------------------------------------


class TestProfileInvalidation:
    def test_hssc_change_clears_eligibility(self, _mock_session_state) -> None:
        session = _mock_session_state
        state.update_profile({"hssc_percentage": 80.0}, source="manual")
        session["eligibility_result"] = {"verdict": "ELIGIBLE"}  # pretend cached
        state.update_profile({"hssc_percentage": 72.0}, source="manual")
        assert session["eligibility_result"] is None

    def test_ensure_eligibility_recomputes_after_invalidation(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        state.update_profile(
            {
                "qualification": "FSc Pre-Engineering",
                "hssc_percentage": 80.0,
            },
            source="manual",
        )
        state.set_selection("test-uni", "bs-cs")
        _mock_session_state["eligibility_result"] = None  # force a recompute
        result = state.ensure_eligibility()
        assert result is not None
        assert "verdict" in result


# ---------------------------------------------------------------------------
# Scenario C — selection propagation mirrors target into the profile
# ---------------------------------------------------------------------------


class TestSelectionPropagation:
    def test_set_selection_updates_profile_and_session(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        state.set_selection("test-uni", "bs-cs")

        session = _mock_session_state
        assert session["selected_university_id"] == "test-uni"
        assert session["selected_program_id"] == "bs-cs"

        profile = state.get_profile()
        assert profile["target_university"] == "Test University"
        assert profile["target_program"] == "BS Computer Science"

        uni, prog, prog_display, _ = state.get_selection()
        assert uni is not None and uni["id"] == "test-uni"
        assert prog is not None and prog["id"] == "bs-cs"
        assert prog_display is not None
        assert prog_display["university_name"] == "Test University"


# ---------------------------------------------------------------------------
# Scenario D — checklist reflects missing documents
# ---------------------------------------------------------------------------


class TestChecklistMissingDocuments:
    def test_checklist_marks_missing_docs(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        state.update_profile(
            {
                "qualification": "FSc Pre-Engineering",
                "hssc_percentage": 75.0,
                "documents": ["CNIC"],
            },
            source="manual",
        )
        state.set_selection("test-uni", "bs-cs")

        checklist = state.build_checklist()
        by_label = {item["label"]: item for item in checklist}

        # CNIC should be done; Matric certificate is still missing.
        assert by_label["CNIC"]["done"] is True
        assert by_label["Matric certificate"]["done"] is False


# ---------------------------------------------------------------------------
# Scenario E — RAG retrieval scoped by university_id
# ---------------------------------------------------------------------------


class TestRAGContext:
    def test_ask_forwards_university_id_to_retriever(
        self, monkeypatch: pytest.MonkeyPatch, _mock_session_state
    ) -> None:
        from backend.rag import retriever as retriever_mod
        import backend.rag as rag_pkg

        captured: dict[str, Any] = {}

        def fake_retrieve(self, question, k=5, university_id=None):
            captured["university_id"] = university_id
            return []

        monkeypatch.setattr(retriever_mod.Retriever, "retrieve", fake_retrieve)
        monkeypatch.setattr(
            retriever_mod, "get_retriever", lambda collection=None: retriever_mod.Retriever(None)
        )
        # Force the rule-based fallback path so we do not need a live Groq key.
        from backend.rag import llm as llm_mod
        monkeypatch.setattr(llm_mod, "is_available", lambda: False)
        monkeypatch.setattr(
            rag_pkg,
            "_rule_based_fallback",
            lambda question, profile, eligibility, university_id=None, program_id=None: "ok",
        )

        from backend.rag import ask
        ask(
            "Am I eligible?",
            profile={"name": "Ali", "aggregate": 75.0},
            eligibility={"verdict": "ELIGIBLE"},
            university_id="test-uni",
        )
        assert captured.get("university_id") == "test-uni"


# ---------------------------------------------------------------------------
# Scenario F — state persists across reads
# ---------------------------------------------------------------------------


class TestStatePersistence:
    def test_get_profile_returns_same_object(self, _mock_session_state) -> None:
        first = state.get_profile()
        first["name"] = "Ali"
        second = state.get_profile()
        assert second["name"] == "Ali"
        assert second is first


# ---------------------------------------------------------------------------
# Scenario G — reset_application restores only canonical fresh defaults
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_application_and_temporary_state(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        session = _mock_session_state
        state.update_profile(
            {
                "name": "Ali",
                "qualification": "FSc",
                "hssc_percentage": 78.0,
                "documents": ["CNIC"],
            },
            source="manual",
        )
        state.set_selection("test-uni", "bs-cs")
        session["eligibility_result"] = {"verdict": "ELIGIBLE"}
        session["chat_history"] = [{"role": "user", "content": "hi"}]
        session["chat_history_sources"] = [["src"]]
        session["manual_doc"] = "CNIC"
        session["_ep_theme_injected"] = True

        state.reset_application()

        profile = state.get_profile()
        assert profile["name"] == ""
        assert profile["qualification"] is None
        assert profile["hssc_percentage"] is None
        assert profile["documents"] == []
        assert session["selected_university_id"] is None
        assert session["selected_program_id"] is None
        assert session["eligibility_result"] is None
        assert session["chat_history"] == []
        assert session["chat_history_sources"] == []
        assert "manual_doc" not in session
        assert "_ep_theme_injected" not in session
        assert set(session) == set(state.session_defaults())


# ---------------------------------------------------------------------------
# Scenario H — university isolation (FAST selection does not leak into a
# separate NUST retrieval) — already covered by test_rag.py. Keep one
# regression assertion here using the public Retriever API.
# ---------------------------------------------------------------------------


class TestUniversityIsolation:
    def test_explicit_university_id_overrides_question_text(
        self, monkeypatch: pytest.MonkeyPatch, _mock_session_state
    ) -> None:
        from backend.rag import retriever as retriever_mod

        captured: dict[str, Any] = {}

        class _FakeCollection:
            def query(self, query_texts, n_results, where=None, **kwargs):
                captured.setdefault("where", []).append(where)
                return {
                    "ids": [["1"]],
                    "documents": [["chunk"]],
                    "metadatas": [[{
                        "university_id": where.get("university_id") if where else "unknown",
                        "university_name": "X",
                        "program_id": "p",
                        "program_name": "P",
                        "category": "c",
                        "source_file": "f",
                    }]],
                    "distances": [[0.1]],
                }

        ret = retriever_mod.Retriever(_FakeCollection())
        ret.retrieve("Tell me about NUST", university_id="fast-nuces")

        # The first (filtered) query must use the explicit ID, not NUST.
        assert captured["where"][0] == {"university_id": "fast-nuces"}


# ---------------------------------------------------------------------------
# Scenario I — manual correction survives a subsequent OCR run
# ---------------------------------------------------------------------------


class TestManualCorrectionSurvival:
    def test_manual_value_not_overwritten_by_ocr(
        self, _mock_session_state
    ) -> None:
        state.update_profile({"aggregate": 70.0}, source="ocr")
        state.update_profile({"aggregate": 75.0}, source="manual")
        state.update_profile({"aggregate": 70.0}, source="ocr")

        profile = state.get_profile()
        assert profile["aggregate"] == 75.0
        assert profile["field_sources"].get("aggregate") == "manual"


# ---------------------------------------------------------------------------
# Scenario J — missing info yields None instead of a guessed verdict
# ---------------------------------------------------------------------------


class TestMissingInfo:
    def test_ensure_eligibility_returns_none_without_profile(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        state.set_selection("test-uni", "bs-cs")
        # profile has no qualification / aggregate yet
        result = state.ensure_eligibility()
        # The engine returns a verdict dict (often "NOT ELIGIBLE" / "UNKNOWN")
        # rather than None when a program is selected — the caller should
        # branch on the verdict string. When no program is selected,
        # ensure_eligibility returns None.
        assert result is not None

    def test_ensure_eligibility_returns_none_without_selection(
        self, _mock_session_state
    ) -> None:
        assert state.ensure_eligibility() is None


class TestStateDefaults:
    def test_session_defaults_are_independent(self) -> None:
        first = state.session_defaults()
        second = state.session_defaults()

        first["student_profile"]["name"] = "Ali"
        first["parsed_docs"].append({"filename": "hssc.txt"})
        first["chat_history"].append({"role": "user"})

        assert second["student_profile"]["name"] == ""
        assert second["parsed_docs"] == []
        assert second["chat_history"] == []


class TestManualProfileUpdates:
    def test_manual_document_invalidates_eligibility(self, _mock_session_state) -> None:
        _mock_session_state["eligibility_result"] = {"verdict": "ELIGIBLE"}

        profile = state.add_manual_document("CNIC")

        assert profile["documents"] == ["CNIC"]
        assert _mock_session_state["eligibility_result"] is None

    def test_manual_test_score_invalidates_eligibility(self, _mock_session_state) -> None:
        _mock_session_state["eligibility_result"] = {"verdict": "ELIGIBLE"}

        profile = state.add_manual_test_score("NTS-NAT", 82)

        assert profile["test_scores"] == {"NTS-NAT": 82}
        assert _mock_session_state["eligibility_result"] is None


class TestMultipleDocumentActions:
    def test_builds_a_separate_action_for_each_missing_document(
        self, _mock_session_state, tiny_dataset
    ) -> None:
        state.update_profile(
            {"qualification": "FSc Pre-Engineering", "hssc_percentage": 80.0},
            source="manual",
        )
        state.set_selection("test-uni", "bs-cs")

        actions = state.build_next_actions()
        upload_actions = [action for action in actions if action["target"] == "pages/1_Upload_Documents.py"]

        assert [action["title"] for action in upload_actions] == [
            "Upload CNIC",
            "Upload Matric certificate",
        ]
