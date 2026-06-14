"""Dimension 6 — Inhalt, Aktualität & Conversion (rein, offline).

`analyze(fr, soup)` misst, ob eine Seite zum Geschäft führt (Conversion) und ob
sie gepflegt ist (Aktualität) — die MyWEBSITE-Versprechen «Kontakt/Leads» und
«immer aktuell». Gemessen aus dem bereits geparsten `soup`; der Copyright-Scan
liest zusätzlich den rohen `fr.html`. Kein Netz, vollständig offline testbar.

Sub-Signale [CITED: 03-RESEARCH.md Dim-6]:
- Kontaktpfad  : <form> mit input[type=email]/textarea ODER <a> mit "kontakt"  -> gap
- tel:-Link    : a[href^="tel:"]                                               -> minor
- mailto:-Link : a[href^="mailto:"]                                            -> minor
- Impressum    : <a> mit impressum|rechtliches|datenschutz                     -> gap
- Copyright    : neuestes Jahr aus rohem html; Bänder vs. datetime.now().year  -> ok/gap/severe/minor
- Generator    : <meta name="generator"> mit Legacy-CMS                        -> gap

Faltung (Pattern 2): irgendein severe -> severe; sonst >=1 gap -> gap;
sonst >=2 minor -> gap; sonst ok. Reason = kompakter deutscher Join der
feuernden Nicht-ok-Notizen.

CRITICAL — soup=None (erreichbar, aber kein lesbarer Body: 403/406/429, leerer
Body): NEUTRAL, nicht-wertend (0 Gap-Punkte) — NIE severe. Guard steht ZUERST,
VOR dem fr.html-Copyright-Scan, sonst kippt ein WAF-Block auf Bedarf 5.
"""

from __future__ import annotations

import re

from datetime import datetime

from ..models import DimensionVerdict


# Legacy-Generatoren: alte CMS-Versionen / End-of-Life-Baukästen.
# Anker-/Begrenzungssicher (ReDoS-frei): keine geschachtelten Quantoren.
_LEGACY_GENERATOR = re.compile(
    r"WordPress\s+[1-5]\."
    r"|Joomla!?\s+[123]\."
    r"|Drupal\s+7"
    r"|FrontPage"
    r"|Dreamweaver"
    r"|Mobirise"
    r"|Jimdo",
    re.I,
)

# Copyright-Jahr: ©/&copy;/copyright + bis zu 12 Nicht-Ziffern + 20xx.
# Das {0,12}-Limit ist bewusst begrenzt (ReDoS-Schutz T-03-05).
_COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)[^\d]{0,12}(20\d{2})", re.I)

_CONTACT_LINK = re.compile(r"kontakt", re.I)
_IMPRESSUM = re.compile(r"impressum|rechtliches|datenschutz", re.I)


def analyze(fr, soup) -> DimensionVerdict:
    """Reiner Dimension-6-Befund über `fr` (Copyright-Scan) + geparstes `soup`."""
    # soup=None-Guard ZUERST — vor jedem fr.html-Scan: erreichbar, aber kein Body
    # -> NICHT bewertbar. Neutrales, nicht-wertendes Verdict (0 Gap-Punkte) —
    # KEIN severe, sonst kippt ein WAF-Block fälschlich auf Bedarf 5 (403 != 5).
    if soup is None:
        return DimensionVerdict(6, "ok", "nicht bewertbar (kein HTML)", "n/a")

    now = datetime.now().year

    severe: list[str] = []
    gap: list[str] = []
    minor: list[str] = []

    # Alle <a> einmal einsammeln (href + Text gegen Muster prüfen).
    anchors = soup.find_all("a")

    def _any_anchor(pat: re.Pattern) -> bool:
        for a in anchors:
            blob = (a.get("href") or "") + " " + a.get_text()
            if pat.search(blob):
                return True
        return False

    # 1) Kontaktpfad: Formular mit email-Input/Textarea ODER kontakt-Link.
    has_form = False
    for form in soup.find_all("form"):
        if form.find("input", attrs={"type": "email"}) or form.find("textarea"):
            has_form = True
            break
    if not has_form and not _any_anchor(_CONTACT_LINK):
        gap.append("kein Kontaktformular/-pfad")

    # 2) tel: (minor).
    if not soup.select_one('a[href^="tel:"]'):
        minor.append("kein tel:-Link")

    # 3) mailto: (minor).
    if not soup.select_one('a[href^="mailto:"]'):
        minor.append("kein mailto:-Link")

    # 4) Impressum/Datenschutz (gap).
    if not _any_anchor(_IMPRESSUM):
        gap.append("kein Impressum/Datenschutz")

    # 5) Copyright-Aktualität: neuestes Jahr aus rohem html.
    years = [int(y) for y in re.findall(_COPYRIGHT, fr.html or "")]
    if years:
        year = max(years)
        if year >= now - 1:
            pass  # aktuell -> ok
        elif now - 3 <= year <= now - 2:
            gap.append(f"Copyright {year}, veraltet")
        elif year <= now - 4:
            severe.append(f"Copyright {year}, stark veraltet")
    else:
        minor.append("kein Copyright-Jahr gefunden")

    # 6) Legacy-Generator (gap).
    gen = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    if gen:
        g = gen.get("content") or ""
        if _LEGACY_GENERATOR.search(g):
            gap.append(f"veralteter Generator {g}")

    # Pattern-2-Faltung.
    if severe:
        return DimensionVerdict(6, "severe", "; ".join(severe + gap + minor), "html")
    if gap:
        return DimensionVerdict(6, "gap", "; ".join(gap + minor), "html")
    if len(minor) >= 2:
        return DimensionVerdict(6, "gap", "; ".join(minor), "html")
    if minor:
        # einzelnes minor -> noch ok, aber Notiz mitgeben.
        return DimensionVerdict(6, "ok", f"Kontakt, Impressum, aktuell ({minor[0]})", "html")
    return DimensionVerdict(6, "ok", "Kontakt, Impressum, aktuell", "html")
