"""Tests für reasons.build — nachvollziehbare Begründung pro Kunde (NACH-01/AC6).

build(verdicts) -> kompakter deutscher String, der nur die nicht-ok Dimensionen
mit Befund + treibendem Signal nennt und eine Bedarf-Note anhängt, die aus genau
denselben Verdicts via scoring.bedarf berechnet wird (Score & Text laufen nie
auseinander, T-03-07).
"""

from __future__ import annotations

from lead_analyzer import reasons, scoring
from lead_analyzer.models import DimensionVerdict, PaymentEstimate


def vs(*levels: str) -> list[DimensionVerdict]:
    return [DimensionVerdict(i + 1, lv, "r") for i, lv in enumerate(levels)]


def test_all_ok():
    verdicts = vs("ok", "ok", "ok", "ok", "ok", "ok")
    out = reasons.build(verdicts)
    assert "alle Dimensionen ok" in out
    assert "Bedarf 1" in out


def test_mixed_lists_only_driving_dims():
    verdicts = [
        DimensionVerdict(1, "ok", "solide"),
        DimensionVerdict(2, "severe", "Gratis-Subdomain wixsite.com"),
        DimensionVerdict(3, "ok", "ok"),
        DimensionVerdict(4, "gap", "keine Meta-Description"),
        DimensionVerdict(5, "ok", "ok"),
        DimensionVerdict(6, "gap", "Copyright 2021, veraltet"),
    ]
    out = reasons.build(verdicts)
    # treibende Dims genannt
    assert "Dim2" in out
    assert "Dim4" in out
    assert "Dim6" in out
    # Reason-Notizen genannt
    assert "wixsite.com" in out
    assert "Meta-Description" in out
    assert "veraltet" in out
    # ok-Dims NICHT gelistet
    assert "Dim1" not in out
    assert "Dim3" not in out
    assert "Dim5" not in out
    # Summary-Bedarf == scoring.bedarf
    assert f"Bedarf {scoring.bedarf(verdicts)}" in out


def test_dead_reflects_bedarf_5():
    verdicts = vs("ok", "ok", "ok", "ok", "ok", "ok")
    verdicts[0].dead = True
    out = reasons.build(verdicts)
    assert "Bedarf 5" in out


def test_length_bounded():
    verdicts = [
        DimensionVerdict(i + 1, "severe", "ein ziemlich langer Befundtext der die Begründung aufbläht " * 2)
        for i in range(6)
    ]
    out = reasons.build(verdicts)
    assert len(out) <= 210


def test_bedarf_number_matches_scoring_two_cases():
    case_a = vs("gap", "gap", "ok", "ok", "ok", "ok")  # -> 3
    case_b = vs("severe", "severe", "severe", "ok", "ok", "ok")  # -> 5
    assert f"Bedarf {scoring.bedarf(case_a)}" in reasons.build(case_a)
    assert f"Bedarf {scoring.bedarf(case_b)}" in reasons.build(case_b)


# --------------------------------------------------------------------------- #
# Phase 4: optionale Zahlungskräftigkeit-Sektion + Per-Sektion-Cap            #
# --------------------------------------------------------------------------- #

def test_build_with_payment():
    """build(verdicts, payment) trägt BEIDE Rationale, verbunden mit ' | '."""
    verdicts = vs("gap", "gap", "ok", "ok", "ok", "ok")
    pay = PaymentEstimate(4, "Zahl (Schätzung): Rechtsform AG aus Firmenname angenommen")
    out = reasons.build(verdicts, payment=pay)
    assert f"Bedarf {scoring.bedarf(verdicts)}" in out
    assert "Zahl (Schätzung): Rechtsform AG" in out
    assert " | " in out


def test_build_without_payment_unchanged():
    """payment=None -> byte-für-byte wie heute (back-compat); kein 'Zahl'-Text."""
    verdicts = vs("gap", "gap", "ok", "ok", "ok", "ok")
    assert reasons.build(verdicts) == reasons.build(verdicts, None)
    assert "Zahl" not in reasons.build(verdicts)


def test_payment_section_not_truncated():
    """Per-Sektion-Cap: langer Bedarf-Body UND lange zahl-reason -> beide überleben."""
    verdicts = [
        DimensionVerdict(i + 1, "severe", "ein ziemlich langer Befundtext der die Begründung aufbläht " * 2)
        for i in range(6)
    ]
    pay = PaymentEstimate(
        5,
        "Zahl (Schätzung): " + ("Rechtsform AG angenommen; Branchen-Tier hoch; mehrere Standorte; " * 5),
    )
    out = reasons.build(verdicts, payment=pay)
    assert "Zahl (Schätzung):" in out   # zahl-Prefix nicht weggekappt
    assert "Bedarf" in out              # Bedarf-Summary überlebt
