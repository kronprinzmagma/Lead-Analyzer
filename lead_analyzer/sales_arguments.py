"""Deterministic sales-argument builder (Phase 9 / DIFF-04 / NACH-01).

Pure module — no I/O, no network, no external dependencies, never raises.
Converts each company's measured dimension deficits (RowResult.verdicts) into
positive, sales-ready arguments for a modern website solution, written into the
second output sheet ("Verkaufsargumente").

The mapping table (_MAPPING) is the single source of truth for the argument text
— edit wording here, in one place. Deficit drivers are determined using the EXACT
same predicate as lead_analyzer.reasons.build():
    drivers = [v for v in verdicts if v.level != "ok" or v.dead]
so the argument sheet and the Begründung column can NEVER disagree (NACH-01).

The arguments describe generic capabilities of a modern, professional website
solution (own domain, SSL, responsive design, SEO, structured content, contact
features) — deliberately product-neutral.
"""

from __future__ import annotations

from .models import RowRecord, RowResult

# ---------- Module-level constants ----------

# THE MAPPING — single source of truth (dim → deficit label, solution, benefit).
# Key: dimension number 1..6. Values: defizit, funktion (solution), nutzen (benefit).
# Product-neutral wording: describes what a modern website solution provides.
_MAPPING: dict[int, dict[str, str]] = {
    1: {
        "defizit": "Keine/defekte Website oder nur Social Media",
        "funktion": "Professionelle eigene Website mit eigener Domain",
        "nutzen": "Überhaupt seriös online & auf Google auffindbar — statt nur Social-Profil oder gar nichts",
    },
    2: {
        "defizit": "Kein HTTPS/SSL oder nur Gratis-Subdomain",
        "funktion": "SSL-Verschlüsselung + eigene Domain (statt Gratis-Subdomain)",
        "nutzen": 'Kein „Nicht sicher“-Warnhinweis im Browser; eigene Adresse statt wixsite.com = Vertrauen & Seriosität',
    },
    3: {
        "defizit": "Nicht für Smartphones optimiert / langsam",
        "funktion": "Responsive Design (passt sich automatisch an Handy/Tablet/PC an)",
        "nutzen": "Erreicht die Mehrheit der Besucher am Handy → weniger Absprünge, mehr Anfragen",
    },
    4: {
        "defizit": "Schlecht auf Google auffindbar (Title/Meta/Indexierung)",
        "funktion": "Professionelle SEO + suchmaschinenoptimierte Inhalte",
        "nutzen": "Wird gefunden, wenn nach dem Angebot gesucht wird → qualifizierte Anfragen ohne Werbebudget",
    },
    5: {
        "defizit": "Nicht KI-/Answer-Engine-bereit (kein strukturiertes Markup)",
        "funktion": "Strukturierte Inhalte & Markup für KI-/Answer-Engines",
        "nutzen": "Auch in KI-Suchen (ChatGPT, Google AI) sichtbar → zukunftssicher auffindbar",
    },
    6: {
        "defizit": "Kaum Kontaktmöglichkeiten / veraltete Inhalte",
        "funktion": "Integrierte Kontakt-/Chat-Funktionen, einfache Pflege, aktuelle Inhalte",
        "nutzen": "Besucher werden zu Anfragen & Kunden; stets aktuelle Inhalte → mehr Abschlüsse",
    },
}

# Honest note for companies with no measurable deficits (Bedarf 1 / all ok).
# Never invent a deficit — this is the correct answer for modern sites.
NO_DEFICIT_NOTE: str = (
    "Keine akuten Defizite — moderne Website über alle Dimensionen. "
    "Ansatz: Stärken sichern (Pflege/Aktualität) bzw. ausbauen (E-Shop, Terminbuchung)."
)


# ---------- Builder ----------

def build_arguments(
    record: RowRecord | None,
    result: RowResult,
    url_value: object = None,
) -> tuple[str, str, str]:
    """Build sales arguments from a company's measured deficits.

    Returns (kundenname, defizite_text, funktionen_text).

    - kundenname: from "Kundenname" cell; falls back to url_value; falls back to
      "Zeile {index+1}".
    - defizite_text: newline-joined bullet list of deficit labels for non-ok/dead
      verdicts.  Empty string for the no-deficit case.
    - funktionen_text: newline-joined "• {funktion} → {nutzen}" per deficit dim, OR
      NO_DEFICIT_NOTE when there are no deficits.

    Uses the EXACT reasons.py driver predicate (NACH-01):
        drivers = [v for v in verdicts if v.level != "ok" or v.dead]

    Edge cases:
    - empty verdicts + bedarf==5 (empty URL / exception path): treat as dim-1 deficit.
    - empty verdicts + bedarf!=5: no-deficit case → NO_DEFICIT_NOTE.
    - any cell weirdness: fully defensive via try/except; never raises (T-09-01).
    """
    try:
        # --- Kundenname resolution ---
        name = str((record.cells.get("Kundenname") if record else None) or "")
        if not name:
            name = str(url_value or "")
        if not name:
            idx = record.index if record is not None else 0
            name = f"Zeile {idx + 1}"

        # --- Deficit driver determination (NACH-01: verbatim reasons.py predicate) ---
        verdicts = result.verdicts or []
        drivers = [v for v in verdicts if v.level != "ok" or v.dead]

        # Edge case: empty verdicts on broken-URL / exception path
        if not drivers and result.bedarf == 5:
            deficit_dims = [1]
        elif not drivers:
            # No deficits at all — honest note, no invented deficit
            return (name, "", NO_DEFICIT_NOTE)
        else:
            # Collect unique dims in ascending order
            seen: set[int] = set()
            deficit_dims = []
            for v in drivers:
                if v.dim not in seen and v.dim in _MAPPING:
                    seen.add(v.dim)
                    deficit_dims.append(v.dim)
            deficit_dims.sort()

        # --- Build text columns ---
        defizite_lines = []
        funktionen_lines = []
        for d in deficit_dims:
            entry = _MAPPING.get(d)
            if entry is None:
                continue  # defensive: clamp to 1..6; skip unknown dims
            defizite_lines.append(f"• {entry['defizit']}")
            funktionen_lines.append(f"• {entry['funktion']} → {entry['nutzen']}")

        defizite_text = "\n".join(defizite_lines)
        funktionen_text = "\n".join(funktionen_lines)
        return (name, defizite_text, funktionen_text)

    except Exception:
        # T-09-01: exception-free — a weird row must never break output generation.
        safe_name = f"Zeile {(record.index + 1) if record is not None else 1}"
        return (safe_name, "", NO_DEFICIT_NOTE)
