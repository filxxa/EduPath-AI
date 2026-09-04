"""Tests for the merit calculation engine (backend/merit.py)."""
from __future__ import annotations

import pytest

from backend.merit import (
    calculate_merit,
    get_merit_formula,
    parse_formula,
)


# ── Fixtures ───────────────────────────────────────────────────────

def _make_data(programs: list[dict] | None = None, uni_id: str = "fast-nuces") -> dict:
    return {
        "metadata": {},
        "universities": [
            {
                "id": uni_id,
                "name": "FAST-NUCES",
                "programs": programs or [],
            }
        ],
    }


def _prog(pid: str, formula: str | None, admission_test: str = "FAST-NUCES / SAT / NTS NAT-IE") -> dict:
    reqs: dict = {"admission_test": admission_test}
    if formula is not None:
        reqs["aggregate_formula"] = formula
    return {"id": pid, "name": f"Program {pid}", "requirements": reqs}


FAST_BUSINESS_FORMULA = "10% SSC + 40% HSSC/equivalent + 50% admission test"
FAST_ENGINEERING_FORMULA = "17% SSC + 50% HSSC/equivalent + 33% admission test"


def _full_profile(**overrides) -> dict:
    base = {
        "hssc_percentage": 82.0,
        "ssc_percentage": 88.0,
        "test_scores": {"NAT-IE": 75.0},
        "aggregate": 80.0,
    }
    base.update(overrides)
    return base


# ── parse_formula ──────────────────────────────────────────────────

class TestParseFormula:
    def test_basic_three_components(self):
        components = parse_formula(FAST_BUSINESS_FORMULA)
        assert len(components) == 3
        assert components[0]["name"] == "SSC"
        assert components[0]["weight"] == 10.0
        assert components[0]["source"] == "ssc_percentage"
        assert components[1]["name"] == "HSSC/equivalent"
        assert components[1]["weight"] == 40.0
        assert components[1]["source"] == "hssc_percentage"
        assert components[2]["name"] == "admission test"
        assert components[2]["weight"] == 50.0
        assert components[2]["source"] == "admission_test"

    def test_engineering_formula(self):
        components = parse_formula(FAST_ENGINEERING_FORMULA)
        assert len(components) == 3
        weights = [c["weight"] for c in components]
        assert sum(weights) == 100.0

    def test_empty_string(self):
        assert parse_formula("") == []

    def test_garbage_input(self):
        assert parse_formula("no percentages here") == []


# ── get_merit_formula ──────────────────────────────────────────────

class TestGetMeritFormula:
    def test_returns_formula_when_present(self):
        data = _make_data([_prog("bs-cs", FAST_BUSINESS_FORMULA)])
        result = get_merit_formula("fast-nuces", "bs-cs", data)
        assert result is not None
        assert result["formula_string"] == FAST_BUSINESS_FORMULA
        assert len(result["components"]) == 3

    def test_returns_none_when_no_formula(self):
        data = _make_data([_prog("bs-cs", None)])
        assert get_merit_formula("fast-nuces", "bs-cs", data) is None

    def test_returns_none_for_unknown_university(self):
        data = _make_data([])
        assert get_merit_formula("no-uni", "no-prog", data) is None

    def test_returns_none_for_unknown_program(self):
        data = _make_data([_prog("bs-cs", FAST_BUSINESS_FORMULA)])
        assert get_merit_formula("fast-nuces", "no-prog", data) is None


# ── calculate_merit — complete ─────────────────────────────────────

class TestCalculateMeritComplete:
    def test_full_calculation_business_formula(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile()
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        assert result["merit"] is not None
        assert result["missing"] == []
        assert len(result["components"]) == 3

        ssc = next(c for c in result["components"] if c["source"] == "ssc_percentage")
        hssc = next(c for c in result["components"] if c["source"] == "hssc_percentage")
        test = next(c for c in result["components"] if c["source"] == "admission_test")

        assert ssc["percentage"] == 88.0
        assert ssc["weighted_score"] == 8.8
        assert hssc["percentage"] == 82.0
        assert hssc["weighted_score"] == 32.8
        assert test["percentage"] == 75.0
        assert test["weighted_score"] == 37.5

        assert result["merit"] == round(8.8 + 32.8 + 37.5, 2)

    def test_full_calculation_engineering_formula(self):
        data = _make_data([_prog("bs-ce", FAST_ENGINEERING_FORMULA)])
        profile = _full_profile()
        result = calculate_merit(profile, "fast-nuces", "bs-ce", data)

        assert result["status"] == "complete"
        ssc = next(c for c in result["components"] if c["source"] == "ssc_percentage")
        hssc = next(c for c in result["components"] if c["source"] == "hssc_percentage")
        test = next(c for c in result["components"] if c["source"] == "admission_test")

        assert ssc["weighted_score"] == round(88.0 * 17 / 100, 2)
        assert hssc["weighted_score"] == round(82.0 * 50 / 100, 2)
        assert test["weighted_score"] == round(75.0 * 33 / 100, 2)
        expected = ssc["weighted_score"] + hssc["weighted_score"] + test["weighted_score"]
        assert result["merit"] == round(expected, 2)


# ── Missing data ───────────────────────────────────────────────────

class TestMissingData:
    def test_missing_hssc(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(hssc_percentage=None)
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "incomplete"
        assert result["merit"] is None
        assert "HSSC/equivalent" in result["missing"]
        hssc_comp = next(c for c in result["components"] if c["source"] == "hssc_percentage")
        assert hssc_comp["available"] is False
        assert hssc_comp["percentage"] is None

    def test_missing_ssc(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(ssc_percentage=None)
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "incomplete"
        assert result["merit"] is None
        assert "SSC" in result["missing"]

    def test_missing_admission_test(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(test_scores={})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "incomplete"
        assert result["merit"] is None
        assert "admission test" in result["missing"]

    def test_all_missing(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(hssc_percentage=None, ssc_percentage=None, test_scores={})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "incomplete"
        assert result["merit"] is None
        assert len(result["missing"]) == 3


# ── Test score handling ────────────────────────────────────────────

class TestScoreHandling:
    def test_score_with_slash_max_not_100(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(test_scores={"NAT-IE": "120/200"})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        test_comp = next(c for c in result["components"] if c["source"] == "admission_test")
        assert test_comp["percentage"] == 60.0
        assert test_comp["weighted_score"] == 30.0

    def test_score_as_string_percentage(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(test_scores={"NAT-IE": "75"})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        test_comp = next(c for c in result["components"] if c["source"] == "admission_test")
        assert test_comp["percentage"] == 75.0

    def test_score_with_percent_sign(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(test_scores={"NAT-IE": "82%"})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        test_comp = next(c for c in result["components"] if c["source"] == "admission_test")
        assert test_comp["percentage"] == 82.0

    def test_partial_match_test_name(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(test_scores={"NTS-NAT-IE": 70.0})
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        test_comp = next(c for c in result["components"] if c["source"] == "admission_test")
        assert test_comp["percentage"] == 70.0


# ── Formula unavailable ───────────────────────────────────────────

class TestFormulaUnavailable:
    def test_no_formula_in_program(self):
        data = _make_data([_prog("bs-cs", None)])
        profile = _full_profile()
        result = calculate_merit(profile, "fast-nuces", "bs-cs", data)

        assert result["status"] == "unavailable"
        assert result["merit"] is None
        assert result["components"] == []
        assert result["formula_string"] is None

    def test_unknown_university(self):
        data = _make_data([])
        result = calculate_merit(_full_profile(), "unknown", "unknown", data)
        assert result["status"] == "unavailable"


# ── Weight totals ──────────────────────────────────────────────────

class TestWeightTotals:
    def test_weights_not_100(self):
        formula = "20% SSC + 30% HSSC/equivalent + 40% admission test"
        data = _make_data([_prog("bba", formula)])
        profile = _full_profile()
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        assert result["weight_total"] == 90.0
        assert result["merit"] is not None

    def test_weights_over_100(self):
        formula = "50% SSC + 50% HSSC/equivalent + 20% admission test"
        data = _make_data([_prog("bba", formula)])
        profile = _full_profile()
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["weight_total"] == 120.0
        assert result["status"] == "complete"


# ── Decimal percentages ───────────────────────────────────────────

class TestDecimalPercentages:
    def test_decimal_hssc_and_ssc(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(hssc_percentage=77.73, ssc_percentage=88.55)
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        hssc = next(c for c in result["components"] if c["source"] == "hssc_percentage")
        ssc = next(c for c in result["components"] if c["source"] == "ssc_percentage")
        assert hssc["percentage"] == 77.73
        assert ssc["percentage"] == 88.55
        assert hssc["weighted_score"] == round(77.73 * 40 / 100, 2)
        assert ssc["weighted_score"] == round(88.55 * 10 / 100, 2)


# ── Manual profile values ─────────────────────────────────────────

class TestManualValues:
    def test_manual_profile_values_used(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(
            hssc_percentage=90.0,
            ssc_percentage=95.0,
            test_scores={"NAT-IE": 88.0},
        )
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        assert result["merit"] == round(95 * 0.10 + 90 * 0.40 + 88 * 0.50, 2)

    def test_string_numeric_values_converted(self):
        data = _make_data([_prog("bba", FAST_BUSINESS_FORMULA)])
        profile = _full_profile(hssc_percentage="82.5", ssc_percentage="88.0")
        result = calculate_merit(profile, "fast-nuces", "bba", data)

        assert result["status"] == "complete"
        hssc = next(c for c in result["components"] if c["source"] == "hssc_percentage")
        assert hssc["percentage"] == 82.5


# ── Different formulas ────────────────────────────────────────────

class TestDifferentFormulas:
    def test_two_different_programs_different_formulas(self):
        data = _make_data([
            _prog("bba", FAST_BUSINESS_FORMULA),
            _prog("bs-ce", FAST_ENGINEERING_FORMULA),
        ])
        profile = _full_profile()

        biz = calculate_merit(profile, "fast-nuces", "bba", data)
        eng = calculate_merit(profile, "fast-nuces", "bs-ce", data)

        assert biz["status"] == "complete"
        assert eng["status"] == "complete"
        assert biz["merit"] != eng["merit"]

        ssc_biz = next(c for c in biz["components"] if c["source"] == "ssc_percentage")
        ssc_eng = next(c for c in eng["components"] if c["source"] == "ssc_percentage")
        assert ssc_biz["weight"] == 10.0
        assert ssc_eng["weight"] == 17.0


# ── effective_aggregate precedence ──────────────────────────────────


class TestEffectiveAggregate:
    def test_entry_test_score_takes_precedence_over_hssc(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {"NAT-IE": 85.0},
            "hssc_percentage": 78.0,
            "aggregate": 80.0,
        }
        assert effective_aggregate(profile) == 85.0

    def test_hssc_used_when_no_test_scores(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {},
            "hssc_percentage": 78.0,
            "aggregate": 80.0,
        }
        assert effective_aggregate(profile) == 78.0

    def test_aggregate_used_when_no_test_no_hssc(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {},
            "hssc_percentage": None,
            "aggregate": 80.0,
        }
        assert effective_aggregate(profile) == 80.0

    def test_none_when_nothing_available(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {},
            "hssc_percentage": None,
            "aggregate": None,
        }
        assert effective_aggregate(profile) is None

    def test_string_test_score_converted(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {"NAT-IE": "92"},
            "hssc_percentage": 80.0,
        }
        assert effective_aggregate(profile) == 92.0

    def test_slash_notation_test_score(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {"NAT-IE": "150/200"},
            "hssc_percentage": 80.0,
        }
        assert effective_aggregate(profile) == 75.0

    def test_empty_test_scores_dict_falls_through(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": {},
            "hssc_percentage": 82.5,
            "aggregate": None,
        }
        assert effective_aggregate(profile) == 82.5

    def test_none_test_scores_falls_through(self):
        from backend.profile import effective_aggregate

        profile = {
            "test_scores": None,
            "hssc_percentage": 77.0,
        }
        assert effective_aggregate(profile) == 77.0
