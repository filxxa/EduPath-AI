"""Centralized test-name utilities derived from the university catalog.

Provides data-driven test name options for the Profile dropdown and a fuzzy
matching predicate shared by eligibility, checklist, and merit logic.
"""
from __future__ import annotations

import re
from typing import Any

from backend.data_loader import load_universities


def _cache(fn):
    try:
        import streamlit as st
        return st.cache_data(fn)
    except Exception:
        return fn


_SPLIT_RE = re.compile(r"\s*[/;,]\s*|\s+or\s+")


@_cache
def get_test_name_options() -> list[str]:
    """Return a sorted, deduplicated list of individual test names from the catalog.

    Parses every ``admission_test`` field in ``data/universities.json``, splits
    compound values by ``/``, ``,``, ``;``, and ``or``, strips whitespace, and
    returns unique display-friendly names.  Entries like ``"No ECAT"`` that
    indicate no test is required are excluded.
    """
    data = load_universities()
    seen: dict[str, str] = {}
    for university in data.get("universities", []):
        for program in university.get("programs", []):
            raw = program.get("requirements", {}).get("admission_test", "")
            if not raw:
                continue
            for token in _SPLIT_RE.split(raw):
                token = token.strip()
                if not token:
                    continue
                token_lower = token.lower()
                if token_lower.startswith("no "):
                    continue
                if "required" in token_lower and not _looks_like_test_name(token):
                    continue
                key = token_lower
                if key not in seen:
                    seen[key] = token
    return sorted(seen.values(), key=str.lower)


def _looks_like_test_name(token: str) -> bool:
    """Heuristic: does this token look like an actual test name?"""
    test_keywords = {"test", "sat", "act", "ecat", "nat", "nts", "net", "lcat", "muet"}
    lower = token.lower()
    return any(kw in lower for kw in test_keywords)


def _split_admission_field(field: str) -> list[str]:
    """Split an admission_test field into individual accepted test tokens."""
    tokens = []
    for token in _SPLIT_RE.split(field):
        token = token.strip()
        if token and not token.lower().startswith("no "):
            tokens.append(token)
    return tokens


def matches_test_name(student_keys: set[str], admission_test_field: str) -> bool:
    """Return whether any student test-score key fuzzily matches the admission field.

    Splits ``admission_test_field`` by ``/``, ``,``, ``;``, and ``or``.  For each
    accepted token, checks whether any student key is a case-insensitive
    substring of the token or vice versa.  This mirrors the matching logic in
    ``merit.py:_resolve_test_score`` so eligibility, checklists, and merit
    calculations agree.
    """
    if not student_keys or not admission_test_field:
        return False

    accepted = _split_admission_field(admission_test_field)
    if not accepted:
        return False

    student_lower = {k.lower().strip() for k in student_keys if k.strip()}

    for token in accepted:
        token_lower = token.lower().strip()
        for student_key in student_lower:
            if not student_key:
                continue
            if student_key == token_lower:
                return True
            if student_key in token_lower or token_lower in student_key:
                return True
    return False
