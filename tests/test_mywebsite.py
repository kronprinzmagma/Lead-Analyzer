"""Wave-0 RED tests for lead_analyzer.mywebsite — mapping + builder unit tests.

These tests MUST FAIL before mywebsite.py is implemented (RED phase).
They serve as the specification for Task 2 (GREEN implementation).

Requirements covered:
- DIFF-04: each dimension's gap/severe verdict → its mapped Funktion+Nutzen
- DIFF-04: empty verdicts + bedarf 5 → dim-1 "no website" argument
- DIFF-04: all-ok (Bedarf 1) → "keine akuten Defizite" note, no invented deficit
- DIFF-04: Kundenname fallback (no name column → URL / row index)
- NACH-01: deficits trace to same verdict drivers as reasons.build
"""

from __future__ import annotations

import pytest

from lead_analyzer.mywebsite import NO_DEFICIT_NOTE, _MAPPING, build_arguments
from lead_analyzer.models import DimensionVerdict, RowRecord, RowResult


def _record(index: int = 0, cells: dict | None = None) -> RowRecord:
    return RowRecord(index=index, cells=cells or {})


def _verdict(dim: int, level: str = "gap", reason: str = "x", dead: bool = False) -> DimensionVerdict:
    return DimensionVerdict(dim=dim, level=level, reason=reason, dead=dead)


def _result(verdicts=None, bedarf: int = 3, zahl: int = 3) -> RowResult:
    return RowResult(index=0, bedarf=bedarf, zahl=zahl, verdicts=verdicts or [])


# ---------- test_each_dimension_maps (DIFF-04) ----------

@pytest.mark.parametrize("dim", [1, 2, 3, 4, 5, 6])
def test_each_dimension_maps(dim):
    """Each of dims 1..6 maps to its Funktion + Nutzen."""
    record = _record(cells={"Kundenname": f"Firma Dim{dim}"})
    result = _result(verdicts=[_verdict(dim=dim, level="gap")])
    kundenname, defizite_text, funktionen_text = build_arguments(record, result)

    assert kundenname == f"Firma Dim{dim}"
    assert _MAPPING[dim]["defizit"] in defizite_text
    assert _MAPPING[dim]["funktion"] in funktionen_text
    assert _MAPPING[dim]["nutzen"] in funktionen_text


# ---------- test_empty_verdicts_no_website (DIFF-04 edge case) ----------

def test_empty_verdicts_no_website():
    """Empty verdicts + bedarf=5 → dim-1 'no reachable website' argument."""
    record = _record(cells={"Kundenname": "Kiosk Bahnhof"})
    result = _result(verdicts=[], bedarf=5)
    _, defizite_text, funktionen_text = build_arguments(record, result)

    assert _MAPPING[1]["defizit"] in defizite_text
    assert _MAPPING[1]["funktion"] in funktionen_text


# ---------- test_no_deficit_note (DIFF-04 / NACH-01) ----------

def test_no_deficit_note():
    """All verdicts ok, bedarf=1 → NO_DEFICIT_NOTE; never an invented deficit."""
    record = _record(cells={"Kundenname": "Profi AG"})
    verdicts = [_verdict(dim=d, level="ok") for d in range(1, 7)]
    result = _result(verdicts=verdicts, bedarf=1)
    _, defizite_text, funktionen_text = build_arguments(record, result)

    # Defizite should be empty (no deficits)
    assert defizite_text == ""
    # Funktionen should be the honest no-deficit note
    assert funktionen_text == NO_DEFICIT_NOTE
    # The note must start with the agreed string
    assert NO_DEFICIT_NOTE.startswith("Keine akuten Defizite")


# ---------- test_name_fallback (DIFF-04) ----------

def test_name_fallback_url():
    """No 'Kundenname' cell but URL value → kundenname falls back to the URL string."""
    record = RowRecord(index=0, cells={"Website": "https://example.ch"})
    result = _result(verdicts=[_verdict(dim=2, level="gap")], bedarf=3)
    kundenname, _, _ = build_arguments(record, result, url_value="https://example.ch")

    assert kundenname == "https://example.ch"


def test_name_fallback_row_index():
    """No 'Kundenname' and no URL → kundenname falls back to 'Zeile {index+1}'."""
    record = RowRecord(index=4, cells={})
    result = _result(verdicts=[_verdict(dim=3, level="gap")], bedarf=3)
    kundenname, _, _ = build_arguments(record, result, url_value=None)

    assert kundenname == "Zeile 5"


# ---------- test_deficits_match_reason_drivers (NACH-01) ----------

def test_deficits_match_reason_drivers():
    """Deficit dims == [v.dim for v in verdicts if v.level != 'ok' or v.dead]."""
    verdicts = [
        _verdict(dim=1, level="ok"),        # not a driver
        _verdict(dim=2, level="gap"),        # driver
        _verdict(dim=3, level="severe"),     # driver
        _verdict(dim=4, level="ok"),         # not a driver
        _verdict(dim=5, level="ok", dead=True),  # driver (dead=True overrides)
        _verdict(dim=6, level="gap"),        # driver
    ]
    record = _record(cells={"Kundenname": "Mix AG"})
    result = _result(verdicts=verdicts, bedarf=4)
    _, defizite_text, _ = build_arguments(record, result)

    # Expected drivers from the exact reasons.py predicate
    expected_drivers = [v for v in verdicts if v.level != "ok" or v.dead]
    expected_dims = sorted({v.dim for v in expected_drivers})

    # Verify each expected deficit label is in the defizite_text
    for dim in expected_dims:
        assert _MAPPING[dim]["defizit"] in defizite_text, (
            f"dim {dim} deficit label missing from defizite_text"
        )

    # Verify no unexpected dim appears
    for dim in [1, 4]:  # ok-only, not dead
        assert _MAPPING[dim]["defizit"] not in defizite_text, (
            f"dim {dim} (ok, not dead) should NOT appear in defizite_text"
        )
