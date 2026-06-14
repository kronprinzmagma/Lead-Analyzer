"""Tests für die echte 6-Dimensionen-Aggregation scoring.bedarf (BED-07/BED-08).

BED-07: deterministische Band-Zuordnung gemäss docs/scoring_website_bedarf.md
        (G = Gap-Punkte, S = Severe-Anzahl, dead-Override -> 5).
BED-08: Monotonie/Richtung (AC3) — jede zusätzliche Lücke hebt oder hält den Score,
        all-ok -> 1, all-severe/dead -> 5; Ergebnis stets int in 1..5.
"""

from __future__ import annotations

import pytest

from lead_analyzer import scoring
from lead_analyzer.models import DimensionVerdict


def vs(*levels: str) -> list[DimensionVerdict]:
    """Baut eine Verdict-Liste aus Levels: vs('ok','gap',...) -> Dim 1..n."""
    return [DimensionVerdict(i + 1, lv, "r") for i, lv in enumerate(levels)]


# --------------------------------------------------------------------------- #
# BED-07: Band-Zuordnung (jedes Band + Grenzen)                                #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "verdicts, expected",
    [
        # G == 0 -> 1 (modern über alle Dimensionen)
        (vs("ok", "ok", "ok", "ok", "ok", "ok"), 1),
        # G == 1 -> 2 (genau eine Lücke)
        (vs("gap", "ok", "ok", "ok", "ok", "ok"), 2),
        # 2 <= G <= 3 -> 3
        (vs("gap", "gap", "ok", "ok", "ok", "ok"), 3),   # G=2
        (vs("gap", "gap", "gap", "ok", "ok", "ok"), 3),  # G=3
        # 4 <= G <= 6 -> 4
        (vs("gap", "gap", "gap", "gap", "ok", "ok"), 4),  # G=4
        (vs("gap", "gap", "gap", "gap", "gap", "gap"), 4),  # G=6
        # G >= 7 -> 5 (drei gaps + zwei severe = 3 + 4 = 7)
        (vs("gap", "gap", "gap", "severe", "severe", "ok"), 5),
    ],
)
def test_gap_bands(verdicts, expected):
    assert scoring.bedarf(verdicts) == expected


@pytest.mark.parametrize(
    "verdicts, expected",
    [
        # S == 1 -> mindestens 3 (severe rest ok: G=2, S=1 -> max(3,3)=3)
        (vs("severe", "ok", "ok", "ok", "ok", "ok"), 3),
        # S == 2 -> 4 (G=4, S=2 -> max(4,4)=4)
        (vs("severe", "severe", "ok", "ok", "ok", "ok"), 4),
        # S == 3 -> 5
        (vs("severe", "severe", "severe", "ok", "ok", "ok"), 5),
    ],
)
def test_severe_bands(verdicts, expected):
    assert scoring.bedarf(verdicts) == expected


def test_dead_override_even_if_all_ok():
    verdicts = vs("ok", "ok", "ok", "ok", "ok", "ok")
    verdicts[0].dead = True
    assert scoring.bedarf(verdicts) == 5


def test_dead_override_on_non_first_dim():
    verdicts = vs("ok", "ok", "ok", "ok", "ok", "ok")
    verdicts[3].dead = True  # Dim 4
    assert scoring.bedarf(verdicts) == 5


# --------------------------------------------------------------------------- #
# BED-08: Monotonie / Richtung (AC3)                                           #
# --------------------------------------------------------------------------- #

def test_monotonic_worsening_gradient():
    """Von all-ok schrittweise verschlechtern: Score darf nie sinken."""
    levels = ["ok"] * 6
    seq = []
    # Erst jede Dim auf gap, dann jede auf severe — fortlaufend schlimmer.
    for i in range(6):
        levels[i] = "gap"
        seq.append(scoring.bedarf([DimensionVerdict(j + 1, lv, "r") for j, lv in enumerate(levels)]))
    for i in range(6):
        levels[i] = "severe"
        seq.append(scoring.bedarf([DimensionVerdict(j + 1, lv, "r") for j, lv in enumerate(levels)]))

    assert scoring.bedarf(vs("ok", "ok", "ok", "ok", "ok", "ok")) == 1
    assert seq == sorted(seq), f"nicht monoton: {seq}"
    assert seq[-1] == 5  # all-severe


def test_all_severe_is_5():
    assert scoring.bedarf(vs("severe", "severe", "severe", "severe", "severe", "severe")) == 5


def test_one_dead_anywhere_is_5():
    verdicts = vs("ok", "gap", "ok", "ok", "ok", "ok")
    verdicts[2].dead = True
    assert scoring.bedarf(verdicts) == 5


def test_always_int_in_range():
    import itertools

    for combo in itertools.product(["ok", "gap", "severe"], repeat=3):
        score = scoring.bedarf(vs(*combo))
        assert isinstance(score, int)
        assert 1 <= score <= 5
