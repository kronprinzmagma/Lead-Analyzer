"""Nachvollziehbare Begründung pro Kunde (NACH-01/AC6).

Single Source of Truth = die sechs DimensionVerdicts: die angezeigte Bedarf-Note
wird aus genau denselben Verdicts via `scoring.bedarf` berechnet, damit Score und
Erklärungstext nie auseinanderlaufen (T-03-07). Es werden nur die nicht-ok
Dimensionen mit Befund-Level + Reason gelistet.

Phase 4: optionale Zahlungskräftigkeit-Sektion. Der Cap ist PER-SEKTION (~160
Zeichen je Sektion), NICHT ein globaler 200er — so kann ein langer Bedarf-Body die
zahl-reason ('Zahl (Schätzung): …') nie wegkürzen (NACH-01: beide Rationale müssen
sichtbar bleiben). [CITED: 04-RESEARCH.md]
"""

from __future__ import annotations

from . import scoring
from .models import DimensionVerdict, PaymentEstimate

_MAX_LEN = 160  # Per-Sektion-Cap (Bedarf-Body bzw. zahl-reason je eigenständig)
_LABEL = {"severe": "schwere Lücke", "gap": "Lücke"}


def _cap(text: str, budget: int) -> str:
    """Kappt einen Sektions-Text auf `budget` Zeichen (mit '…')."""
    if len(text) > budget:
        return text[: max(0, budget - 1)].rstrip() + "…"
    return text


def build(verdicts: list[DimensionVerdict], payment: PaymentEstimate | None = None) -> str:
    """Baut die kompakte deutsche Begründung samt Bedarf-Note (1..5).

    `dead`-Befunde (keine/defekte Website) gelten als treibend, auch wenn ihr
    Level "ok" wäre, damit der Override-Grund sichtbar bleibt.

    payment=None -> exakt das bisherige Verhalten (back-compat). payment gegeben ->
    `f"{bedarf_sektion} | {zahl_sektion}"`; jede Sektion wird UNABHÄNGIG gekappt,
    damit die zahl-reason nie weggekürzt wird (NACH-01).
    """
    score = scoring.bedarf(verdicts)
    drivers = [v for v in verdicts if v.level != "ok" or v.dead]
    if not drivers:
        bedarf_section = f"alle Dimensionen ok → Bedarf {score}"
    else:
        parts = [
            f"Dim{v.dim} {_LABEL.get(v.level, v.level)} ({v.reason})"
            for v in drivers
        ]
        body = "; ".join(parts)
        summary = f" → Bedarf {score}"
        body = _cap(body, _MAX_LEN - len(summary))
        bedarf_section = body + summary

    if payment is None:
        return bedarf_section

    payment_section = _cap(payment.reason, _MAX_LEN)
    return f"{bedarf_section} | {payment_section}"
