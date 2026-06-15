"""Zahlungskräftigkeit-Estimator (rein, offline, deterministisch).

`estimate(record, fr, soup, config)` schätzt die Kaufkraft eines Kunden auf der
Skala 1..5 (höher = mehr Kaufkraft, AC3) aus drei öffentlichen Signal-Gruppen —
jeder Punkt rückführbar auf ein benanntes Signal oder eine gekennzeichnete Annahme
(AC5/AC6 load-bearing). Kein Netz, keine neuen Abhängigkeiten, kein LLM, kein Zefix.

Gruppen [CITED: 04-RESEARCH.md / FEATURES.md groups A/B/C]:
  A — Rechtsform aus dem Firmennamen (AG/SA=+2, GmbH/Sàrl/&Co/KlG=+1, Einzelfirma=0)
  B — Branchen-Tier aus der Branche-Spalte (hoch=+2, mittel=+1, tief=+0)
  C — Grössen-Signale aus dem bereits geparsten soup (Team/Jobs/Standorte, je +1, cap ≤2)

Konservativer Default (resolved-predicate): löst NICHTS auf (kein Rechtsform-Suffix,
Branche unbekannt — leer ODER unbekannt nicht-leer —, kein HTML-Signal), dann
zahl=2 + "dünne Datenlage" — KEINE erfundenen Fakten (AC5).

Zefix (DIFF-01) ist ein künftiger Hook, den KEIN v1-Pfad aufruft.

Pitfall 16 (T-04-03): AG/SA/KlG werden \b-anker UND case-SENSITIV gematcht (kein
re.I), damit 'Magazin GmbH'/'Sagi'/'Casa'/'Sava' nie als AG/SA durchgehen;
GmbH/Sàrl/Einzelfirma dürfen re.I nutzen.
"""

from __future__ import annotations

import re

from .. import scoring
from ..models import PaymentEstimate, ZefixFacts


# --------------------------------------------------------------------------- #
# GROUP A — Rechtsform aus dem Firmennamen                                     #
# --------------------------------------------------------------------------- #

# ORDER MATTERS: AG/SA vor den Partnerschaften prüfen; FIRST match wins.
# AG/SA/KlG case-SENSITIV (KEIN re.I, Pitfall 16); GmbH/Sàrl/Einzelfirma re.I.
# Nur \b-ankert + einfache Alternationen (ReDoS-frei, Spiegel content.py).
_LEGAL = [
    (re.compile(r"\bAG\b"),                "AG",          2),  # Aktiengesellschaft
    (re.compile(r"\bSA\b"),                "SA",          2),  # Romandie-AG
    (re.compile(r"\bGmbH\b", re.I),        "GmbH",        1),
    (re.compile(r"\bS(?:à|a)rl\b", re.I),  "Sàrl",        1),  # Romandie-GmbH
    (re.compile(r"&\s*Co\b", re.I),        "& Co",        1),  # Partnerschaft (lit. '&')
    (re.compile(r"\bKlG\b"),               "KlG",         1),
    (re.compile(r"\bEinzelfirma\b", re.I), "Einzelfirma", 0),
]


def _legal_form(name: str) -> tuple[int, list[str]]:
    """Group A: Rechtsform-Punkte + gekennzeichnete Annahme-Notiz aus dem Namen.

    Erster Treffer der \\b-ankerten Tabelle gewinnt. Einzelfirma -> (0, Notiz);
    kein Treffer -> (0, []) (den All-leer-Fall fängt der konservative Default).
    """
    name = str(name or "")
    for pattern, label, points in _LEGAL:
        if pattern.search(name):
            note = f"Rechtsform {label} aus Firmenname angenommen (Quelle: Firmenname)"
            return points, [note]
    return 0, []


def _legal_form_from_zefix(facts: ZefixFacts) -> tuple[int, list[str]]:
    """Group A from authoritative Zefix data (DIFF-01). Maps legalForm.shortName.de to points.

    Ersetzt _legal_form() wenn zefix_facts vorhanden — KEIN Name-Regex nötig.
    Gleiche Punkte-Tabelle wie _LEGAL, aber Quelle ist autoritativ (AC5).
    """
    lf = facts.legal_form_de
    if lf in ("AG", "SA"):
        pts, label = 2, lf
    elif lf in ("GmbH", "Sàrl", "Sarl", "KlG") or "&" in lf:
        pts, label = 1, lf
    elif lf == "Einzelunternehmen":
        pts, label = 0, lf
    else:
        pts, label = 0, lf   # unbekannte Rechtsform -> konservativ 0, keine erfundenen Fakten (AC5)
    note = f"Rechtsform {label} aus Zefix (autoritativ, Quelle: {facts.uid})"
    return pts, [note]


def _status_modifier(facts: "ZefixFacts | None") -> tuple[int, list[str]]:
    """Post-aggregation penalty for non-active companies (DIFF-01/AC3).

    Angewendet NACH _map_to_1_5: gelöschte AG scored tiefer als aktive GmbH (AC3).
    """
    if facts is None or facts.status == "ACTIVE":
        return 0, []
    if facts.status == "BEING_CANCELLED":
        return -1, [f"Status: in Liquidation (Zefix, {facts.source_url})"]
    if facts.status == "CANCELLED":
        return -2, [f"Status: gelöscht (Zefix, {facts.source_url})"]
    return 0, []


# --------------------------------------------------------------------------- #
# GROUP B — Branchen-Tier aus der Branche-Spalte                              #
# --------------------------------------------------------------------------- #

# Transparente Tier-Map; ein Tier-Keyword muss IN der Branche-Zelle vorkommen.
# Struktur so, dass ein künftiger Config-Override (DIFF-03) ein Einzeiler ist.
_TIER = {
    "zahnarzt": 2, "treuhand": 2, "immobilien": 2, "garage": 2,        # hoch +2
    "schreinerei": 1, "sanitär": 1, "gartenbau": 1, "handwerk": 1,      # mittel +1
    "maler": 1, "confiserie": 1,
    "bäckerei": 0, "coiffeur": 0, "velo": 0, "floristik": 0,            # tief +0
    "detailhandel": 0,
}
_TIER_LABEL = {2: "hoch", 1: "mittel", 0: "tief"}


def _branch_tier(branche: str) -> tuple[int, list[str]]:
    """Group B: Branchen-Tier-Punkte + Notiz aus der Branche-Spalte.

    Leer -> (0, ['Branche unbekannt']). Treffer NUR vorwärts: ein bekanntes
    Tier-Keyword muss IN der Zelle vorkommen (`key in b`) — die umgekehrte
    Richtung würde kurze Müll-Zellen wie 'a' fälschlich auf 'zahnarzt' mappen
    und damit ein Tier erfinden (Code-Review H1 / AC5). Bei mehreren Treffern
    (zusammengesetzte Zelle) gewinnt das HÖCHSTE Tier — nicht die Dict-Reihenfolge
    (Code-Review M1). Unbekannte nicht-leere Branche (z.B. 'Raumfahrt') ->
    (0, ['Branche unbekannt']) — DIESELBE alleinige Notiz wie der leere Fall;
    NIE ein Tier raten (AC5).
    """
    b = str(branche or "").strip().lower()
    if not b:
        return 0, ["Branche unbekannt"]
    matches = [(pts, key) for key, pts in _TIER.items() if key in b]
    if not matches:
        return 0, ["Branche unbekannt"]
    pts, key = max(matches)  # höchstes Tier gewinnt (deterministisch, M1)
    note = f"Branchen-Tier (Annahme): {branche} → {_TIER_LABEL[pts]}"
    return pts, [note]


# --------------------------------------------------------------------------- #
# GROUP C — Grössen-Signale aus dem soup                                       #
# --------------------------------------------------------------------------- #

def _size_signals(soup) -> tuple[int, list[str]]:
    """Group C: Grössen-Signale aus dem bereits geparsten soup (cap ≤2).

    soup=None-Guard ZUERST: erreichbar-aber-kein-Body -> neutral (0, []), NIE
    bestraft (Spiegel content.py). Sonst Team/Jobs/Standorte je +1, Gruppe ≤2.
    """
    if soup is None:
        return 0, []                      # nicht bestraft, nichts erfunden
    pts, notes = 0, []
    hrefs = " ".join(
        ((a.get("href") or "") + " " + a.get_text(" ")) for a in soup.find_all("a")
    ).lower()
    if re.search(r"/team|/mitarbeiter|/ueber-uns|über uns", hrefs):
        pts += 1
        notes.append("Team-/Über-uns-Seite")
    if re.search(r"/jobs|/karriere|offene stellen|stellenangebot", hrefs):
        pts += 1
        notes.append("Karriere-/Jobs-Seite")
    if re.search(r"standorte|filialen", hrefs):
        pts += 1
        notes.append("mehrere Standorte")
    return min(pts, 2), notes             # Group C nudgt, dominiert nicht (cap ≤2)


# --------------------------------------------------------------------------- #
# COMBINE + estimate()                                                         #
# --------------------------------------------------------------------------- #

def _map_to_1_5(total: int) -> int:
    """Combine-Map: Summe A+B+C -> 1..5 (via scoring.clamp_score, AC2)."""
    raw = 5 if total >= 4 else 4 if total == 3 else 3 if total == 2 else 2 if total == 1 else 1
    return scoring.clamp_score(raw)       # garantiert int ∈ [1,5]


def estimate(record, fr, soup, config, zefix_facts=None) -> PaymentEstimate:
    """Schätzt die Zahlungskräftigkeit 1..5 aus den Gruppen A+B+C.

    Orchestriert A (Name/Zefix) + B (Branche) + C (soup). Der `resolved`-Prädikat
    ist die SINGLE SOURCE OF TRUTH: nur wenn IRGENDEIN echtes Signal vorlag, wird
    gemappt; sonst konservativer Default 2 + 'dünne Datenlage'. Eine ALLEINIGE Notiz
    ['Branche unbekannt'] (aus leerer ODER unbekannter nicht-leerer Branche) zählt
    NICHT als Auflösung — kein simpler `if not notes:`-Shortcut (der würde eine
    unbekannte Branche fälschlich als sichere 1 scoren). [CITED: resolved-predicate]

    zefix_facts=None (Default): byte-identisch zur Phase-7-Baseline — alle bestehenden
    Caller bleiben ohne Änderung kompatibel (DIFF-01).
    """
    name = str((record.cells.get("Kundenname") if record else None) or "")
    branche = str((record.cells.get("Branche") if record else None) or "")
    # Group A: Zefix autoritativ > Name-Heuristik (DIFF-01)
    if zefix_facts is not None:
        pa, na = _legal_form_from_zefix(zefix_facts)
    else:
        pa, na = _legal_form(name)
    pb, nb = _branch_tier(branche)
    pc, nc = _size_signals(soup)
    notes = na + nb + nc
    # "dünne Datenlage": kein Namens-Suffix, Branche unbekannt (leer ODER unbekannt
    # nicht-leer -> beide ergeben nb == ['Branche unbekannt']), kein HTML-Signal.
    # zefix_facts vorhanden -> immer resolved (autoritäres Signal, AC5).
    resolved = zefix_facts is not None or bool(na) or pb > 0 or (nb and nb != ["Branche unbekannt"]) or bool(nc)
    if not resolved:
        return PaymentEstimate(2, "Zahl (Schätzung): dünne Datenlage, konservativ geschätzt", [])
    zahl = _map_to_1_5(pa + pb + pc)
    # Status-Modifier nach Aggregation anwenden (DIFF-01/AC3): gelöschte Firma scored tiefer
    penalty, penalty_notes = _status_modifier(zefix_facts)
    zahl = scoring.clamp_score(zahl + penalty)
    notes = notes + penalty_notes
    return PaymentEstimate(zahl, "Zahl (Schätzung): " + "; ".join(notes), notes)
