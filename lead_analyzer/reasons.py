"""Nachvollziehbare Begründung pro Kunde (NACH-01/AC6).

Single Source of Truth = die sechs DimensionVerdicts: die angezeigte Bedarf-Note
wird aus genau denselben Verdicts via `scoring.bedarf` berechnet, damit Score und
Erklärungstext nie auseinanderlaufen (T-03-07). Es werden nur die nicht-ok
Dimensionen mit Befund-Level + Reason gelistet; das Resultat ist auf ~200 Zeichen
gekappt (passt in die Begründungsspalte des Outputs).
"""

from __future__ import annotations

from . import scoring
from .models import DimensionVerdict

_MAX_LEN = 200
_LABEL = {"severe": "schwere Lücke", "gap": "Lücke"}


def build(verdicts: list[DimensionVerdict]) -> str:
    """Baut die kompakte deutsche Begründung samt Bedarf-Note (1..5).

    `dead`-Befunde (keine/defekte Website) gelten als treibend, auch wenn ihr
    Level "ok" wäre, damit der Override-Grund sichtbar bleibt.
    """
    score = scoring.bedarf(verdicts)
    drivers = [v for v in verdicts if v.level != "ok" or v.dead]
    if not drivers:
        return f"alle Dimensionen ok → Bedarf {score}"

    parts = [
        f"Dim{v.dim} {_LABEL.get(v.level, v.level)} ({v.reason})"
        for v in drivers
    ]
    body = "; ".join(parts)
    summary = f" → Bedarf {score}"
    budget = _MAX_LEN - len(summary)
    if len(body) > budget:
        body = body[: max(0, budget - 1)].rstrip() + "…"
    return body + summary
