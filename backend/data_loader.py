"""Load and query the curated university admission dataset."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _cache(fn):
    try:
        import streamlit as st
        return st.cache_data(fn)
    except Exception:
        return fn


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@_cache
def load_universities(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = _repo_root() / "data" / "universities.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_university(universities_data: dict[str, Any], university_id: str) -> dict[str, Any] | None:
    for u in universities_data.get("universities", []):
        if u["id"] == university_id:
            return u
    return None


def get_program(university: dict[str, Any], program_id: str) -> dict[str, Any] | None:
    for p in university.get("programs", []):
        if p["id"] == program_id:
            return p
    return None


def list_universities(universities_data: dict[str, Any]) -> list[dict[str, Any]]:
    return universities_data.get("universities", [])


def list_programs(university: dict[str, Any]) -> list[dict[str, Any]]:
    return university.get("programs", [])
