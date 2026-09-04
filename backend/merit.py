"""Merit / aggregate calculation engine.

Parses ``aggregate_formula`` strings stored in ``data/universities.json`` and
computes weighted merit scores from the student profile.  Only formulas
present in the verified dataset are used — nothing is estimated.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.data_loader import get_program, get_university, load_universities

logger = logging.getLogger(__name__)

_COMPONENT_MAP: dict[str, str] = {
    "hssc": "hssc_percentage",
    "hssc/equivalent": "hssc_percentage",
    "ssc": "ssc_percentage",
    "ssc/equivalent": "ssc_percentage",
    "admission test": "admission_test",
    "entry test": "admission_test",
    "test": "admission_test",
    "ecat": "admission_test",
    "net": "admission_test",
}


def parse_formula(formula_str: str) -> list[dict[str, Any]]:
    """Parse ``"10% SSC + 40% HSSC/equivalent + 50% admission test"``."""
    parts = [p.strip() for p in formula_str.split("+")]
    components: list[dict[str, Any]] = []
    for part in parts:
        match = re.match(r"([\d.]+)\s*%\s*(.+)", part.strip())
        if not match:
            continue
        weight = float(match.group(1))
        raw_name = match.group(2).strip().rstrip(".")
        source = _map_source(raw_name)
        components.append({
            "name": raw_name,
            "source": source,
            "weight": weight,
        })
    return components


def _map_source(component_name: str) -> str:
    key = component_name.lower().strip()
    if key in _COMPONENT_MAP:
        return _COMPONENT_MAP[key]
    for token, source in _COMPONENT_MAP.items():
        if token in key:
            return source
    return component_name.lower().replace(" ", "_")


def get_merit_formula(
    university_id: str,
    program_id: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return structured formula dict or ``None`` when unavailable."""
    if data is None:
        data = load_universities()
    uni = get_university(data, university_id)
    if uni is None:
        return None
    prog = get_program(uni, program_id)
    if prog is None:
        return None
    formula_str = (prog.get("requirements") or {}).get("aggregate_formula")
    if not formula_str:
        return None
    components = parse_formula(formula_str)
    if not components:
        return None
    return {
        "university_id": university_id,
        "program_id": program_id,
        "formula_string": formula_str,
        "components": components,
    }


def _resolve_test_score(
    test_scores: dict[str, Any],
    admission_test_field: str | None,
) -> tuple[float | None, str | None]:
    """Find the best matching test score and return ``(percentage, test_name)``."""
    if not test_scores:
        return None, None

    accepted: list[str] = []
    if admission_test_field:
        accepted = [
            t.strip().lower()
            for t in re.split(r"[/,]", admission_test_field)
            if t.strip()
        ]

    def _to_pct(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            value = value.strip()
            if "/" in value:
                parts = value.split("/")
                try:
                    obtained = float(parts[0].strip())
                    total = float(parts[1].strip())
                    return (obtained / total * 100) if total > 0 else None
                except (ValueError, ZeroDivisionError):
                    return None
            try:
                return float(value.rstrip("%"))
            except ValueError:
                return None
        return None

    if accepted:
        for test_name, score_val in test_scores.items():
            if test_name.lower() in accepted:
                pct = _to_pct(score_val)
                if pct is not None:
                    return pct, test_name
        for test_name, score_val in test_scores.items():
            tn = test_name.lower()
            for acc in accepted:
                if acc in tn or tn in acc:
                    pct = _to_pct(score_val)
                    if pct is not None:
                        return pct, test_name

    first_name, first_val = next(iter(test_scores.items()))
    pct = _to_pct(first_val)
    if pct is not None:
        return pct, first_name
    return None, None


def calculate_merit(
    profile: dict[str, Any],
    university_id: str,
    program_id: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute expected merit for the given selection and profile.

    Returns a dict with ``status`` in ``{"complete", "incomplete", "unavailable"}``.
    """
    formula = get_merit_formula(university_id, program_id, data)
    if formula is None:
        return {
            "status": "unavailable",
            "merit": None,
            "components": [],
            "missing": [],
            "formula_source": None,
            "formula_string": None,
            "weight_total": 0,
        }

    components: list[dict[str, Any]] = []
    missing: list[str] = []
    total_merit = 0.0
    all_present = True

    test_scores = profile.get("test_scores") or {}
    admission_test_field = None

    if data is not None:
        uni = get_university(data, university_id)
        if uni:
            prog = get_program(uni, program_id)
            if prog:
                admission_test_field = (prog.get("requirements") or {}).get("admission_test")

    for comp in formula["components"]:
        source = comp["source"]
        weight = comp["weight"]
        name = comp["name"]

        percentage: float | None = None

        if source == "hssc_percentage":
            percentage = profile.get("hssc_percentage")
        elif source == "ssc_percentage":
            percentage = profile.get("ssc_percentage")
        elif source == "admission_test":
            percentage, _ = _resolve_test_score(test_scores, admission_test_field)
        else:
            percentage = profile.get(source)

        if isinstance(percentage, str):
            try:
                percentage = float(percentage)
            except ValueError:
                percentage = None

        if percentage is None:
            all_present = False
            missing.append(name)
            components.append({
                "name": name,
                "source": source,
                "percentage": None,
                "weight": weight,
                "weighted_score": None,
                "available": False,
            })
        else:
            weighted = round(percentage * weight / 100, 4)
            total_merit += weighted
            components.append({
                "name": name,
                "source": source,
                "percentage": round(percentage, 2),
                "weight": weight,
                "weighted_score": round(weighted, 2),
                "available": True,
            })

    weight_total = sum(c["weight"] for c in formula["components"])

    return {
        "status": "complete" if all_present else "incomplete",
        "merit": round(total_merit, 2) if all_present else None,
        "components": components,
        "missing": missing,
        "formula_source": formula["formula_string"],
        "formula_string": formula["formula_string"],
        "weight_total": weight_total,
    }
