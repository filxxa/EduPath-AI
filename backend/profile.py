"""Student profile management."""
from __future__ import annotations

from typing import Any


def default_profile() -> dict[str, Any]:
    return {
        "name": "",
        "qualification": None,
        "board": None,
        "aggregate": None,
        "documents": [],
        "test_scores": {},
        "notes": "",
    }


def is_profile_complete(profile: dict[str, Any]) -> bool:
    return bool(
        profile.get("qualification")
        and profile.get("board")
        and profile.get("aggregate") is not None
    )


def merge_profile(profile: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    new_profile = {**profile, **updates}
    docs = list(set(new_profile.get("documents", [])))
    new_profile["documents"] = docs
    return new_profile


def add_document(profile: dict[str, Any], doc_type: str) -> dict[str, Any]:
    docs = list(profile.get("documents", []))
    if doc_type not in docs:
        docs.append(doc_type)
    profile["documents"] = docs
    return profile


def add_test_score(profile: dict[str, Any], test_name: str, score: float | str) -> dict[str, Any]:
    scores = dict(profile.get("test_scores", {}))
    scores[test_name] = score
    profile["test_scores"] = scores
    return profile
