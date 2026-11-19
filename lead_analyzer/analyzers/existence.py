"""Dimension 1 — Existenz & Substanz (rein, offline).

`analyze(fr)` wandelt ein `FetchResult` in einen `DimensionVerdict(dim=1, ...)`.
Kein I/O — alle Signale stammen aus dem bereits abgerufenen `FetchResult`, sodass
die Funktion komplett offline mit Fixtures testbar ist.

Prioritäts-Reihenfolge (erster Treffer gewinnt) — exakt aus der RESEARCH-Tabelle:
1. error gesetzt UND kein html  -> severe "nicht erreichbar (...)"  [TOT -> Bedarf 5]
2. status in {403,406,429} oder  -> gap "blockiert – nicht bewertbar", unbewertbar=True
   Status >= 400 mit Challenge-Seite   [Website-Bedarf «nicht bewertbar», Entscheid 2026-11-19]
3. status >= 400 ohne html       -> severe "nicht erreichbar (HTTP ...)" [TOT -> 5]
4. geparkter Host/Marker         -> severe "geparkt/Platzhalter"      [TOT -> 5]
5. Social-Host                   -> severe "Social-only"             [Präsenz, nicht tot]
6. JavaScript-Hülle (SPA)        -> ok "Inhalt per JavaScript geladen – nicht beurteilbar"
   [kein «dünn»-Abzug für leeres Ausliefer-HTML, Entscheid 2026-11-19]
7. dünner Inhalt (<300 Wörter)   -> gap "dünner Inhalt"
8. sonst                         -> ok "erreichbar, Inhalt vorhanden"
"""

from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..models import DimensionVerdict


# Geparkte/Platzhalter-Domains (Host nach www-Strip).  [CITED: FEATURES.md Dim-1]
PARKED_HOSTS = {
    "sedoparking.com",
    "parkingcrew.net",
    "bodis.com",
    "above.com",
    "dan.com",
    "afternic.com",
    "hugedomains.com",
    "domainmarket.com",
}

# Platzhalter-/Parking-/Default-Server-Marker (case-insensitiver Substring).
PARKED_MARKERS = (
    "diese domain",
    "domain parken",
    "domain is for sale",
    "buy this domain",
    "this domain is for sale",
    "website coming soon",
    "under construction",
    "in arbeit",
    "standardseite",
    "apache2 ubuntu default page",
    "welcome to nginx",
    "iis windows server",
)

# Social-only-Hosts (Präsenz existiert, aber keine eigene Website).
SOCIAL_HOSTS = {
    "facebook.com",
    "m.facebook.com",
    "fb.com",
    "instagram.com",
    "linktr.ee",
    "linkedin.com",
    "tiktok.com",
    "t.me",
    "xing.com",
}

_THIN_WORDS = 300

# Challenge-/Sperrseiten von Schutzfiltern (Cloudflare & Co.), die mit 4xx/5xx kommen.
# Kleingeschrieben, Substring-Suche im rohen HTML.
CHALLENGE_MARKERS = (
    "cf-chl",
    "challenge-platform",
    "just a moment...",
    "checking your browser",
    "attention required",
    "access denied",
    "ddos protection",
)

# Typische leere Einhängepunkte von Single-Page-Apps (React, Vue, Next, Nuxt, Gatsby, Angular).
_SPA_MOUNT_IDS = {"root", "app", "__next", "__nuxt", "___gatsby", "svelte"}
_SPA_MAX_WORDS = 50


def is_js_shell(soup) -> bool:
    """True gdw. das ausgelieferte HTML eine leere JavaScript-Hülle ist (Single-Page-App).

    Bedingungen: kaum sichtbarer Text (< 50 Wörter ohne script/style/noscript), mindestens
    ein Skript UND ein typischer leerer Einhängepunkt (`<div id="root">`, `<app-root>`, …)
    oder ein noscript-Hinweis auf JavaScript. Dann lässt sich der Inhalt ohne Browser nicht
    beurteilen; er wird nicht als «dünn» gewertet.
    """
    if soup is None or not soup.find("script"):
        return False
    work = BeautifulSoup(str(soup), "html.parser")
    noscript_js = any("javascript" in n.get_text(" ").lower() for n in work.find_all("noscript"))
    for tag in work(["script", "style", "noscript", "template"]):
        tag.decompose()
    body = work.body or work
    if len(body.get_text(" ", strip=True).split()) >= _SPA_MAX_WORDS:
        return False
    mount = any(
        (el.get("id") or "").lower() in _SPA_MOUNT_IDS and not el.get_text(strip=True)
        for el in body.find_all(True)
    ) or body.find("app-root") is not None
    return mount or noscript_js


def _is_challenge(fr) -> bool:
    """Schutzfilter-Sperre: 403/406/429, oder ein anderer Fehlerstatus mit Challenge-Seite."""
    if fr.status in (403, 406, 429):
        return True
    if fr.status is not None and fr.status >= 400 and fr.html:
        low = fr.html[:20000].lower()
        return any(m in low for m in CHALLENGE_MARKERS)
    return False


def analyze(fr, soup=None) -> DimensionVerdict:
    """Reiner Dimension-1-Befund über ein `FetchResult`.

    `soup` ist optional (fetch-once-parse-many): gibt die Pipeline eine bereits
    geparste BeautifulSoup mit, wird sie wiederverwendet — sonst wird sie hier
    lazy gebaut. Backward compatible: `analyze(fr)` verhält sich unverändert.
    """
    # 1) Keine Antwort von irgendeiner Variante (kein Status) -> tot.
    if fr.status is None and not fr.html:
        detail = fr.error or "kein Body"
        # fr.error kann selbst schon "nicht erreichbar" sein (fetch.py) — dann
        # nicht doppeln, sonst Klartext-Detail in Klammern anhängen.
        reason = "nicht erreichbar" if detail == "nicht erreichbar" else f"nicht erreichbar ({detail})"
        return DimensionVerdict(1, "severe", reason, "html", dead=True)

    # 2) WAF-Block: geantwortet, aber nicht bewertbar -> NICHT Bedarf 5.
    #    Seit 2026-11-19 zusätzlich unbewertbar=True -> «nicht bewertbar» statt Note.
    if _is_challenge(fr):
        return DimensionVerdict(
            1, "gap", f"Abruf blockiert durch Schutzfilter (HTTP {fr.status})", "html",
            unbewertbar=True,
        )

    # 3) Echte HTTP-Fehler ohne Body -> tot.
    if fr.status is not None and fr.status >= 400 and not fr.html:
        return DimensionVerdict(1, "severe", f"nicht erreichbar (HTTP {fr.status})", "html", dead=True)

    # 3b) Host hat geantwortet (Status < 400), aber Body unlesbar -> existiert,
    #     nur nicht bewertbar (Review L2): gap, NICHT tot.
    if not fr.html:
        return DimensionVerdict(1, "gap", f"Antwort ohne lesbaren Body ({fr.error or 'leer'})", "html")

    host = urlsplit(fr.final_url or fr.url or "").netloc.lower().removeprefix("www.")

    text = ""
    title = ""
    if fr.html:
        # parse-once: vor-geparste soup wiederverwenden, sonst lazy bauen.
        # Kopie ziehen, da decompose() die Baumstruktur destruktiv verändert und
        # die geteilte Pipeline-soup intakt bleiben muss (sie geht an Dim 4/5/6).
        base = soup if soup is not None else BeautifulSoup(fr.html, "html.parser")
        work = BeautifulSoup(str(base), "html.parser")
        for tag in work(["script", "style", "nav", "footer"]):
            tag.decompose()
        # get_text() statt .string: greift auch bei verschachteltem Title-Markup.
        title = work.title.get_text(" ", strip=True) if work.title else ""
        text = work.get_text(" ", strip=True)
    # Parking-/Platzhalter-Marker stehen praktisch immer ganz oben; 1024 Zeichen
    # Body reichen und halten den Substring-Scan billig (bewusste Kappung).
    low = (title + " " + text[:1024]).lower()

    # 4) Geparkt (Host oder Marker).
    if host in PARKED_HOSTS or any(m in low for m in PARKED_MARKERS):
        return DimensionVerdict(1, "severe", "geparkt/Platzhalter", "html", dead=True)

    # 5) Social-only.
    if host in SOCIAL_HOSTS:
        return DimensionVerdict(1, "severe", "Social-only", "html")

    # 6) JavaScript-Hülle: Inhalt erst im Browser -> nicht beurteilbar, kein «dünn»-Abzug.
    if is_js_shell(base):
        return DimensionVerdict(1, "ok", "Inhalt per JavaScript geladen – nicht beurteilbar", "html")

    # 7) Dünner Inhalt.
    if len(text.split()) < _THIN_WORDS:
        return DimensionVerdict(1, "gap", "dünner Inhalt", "html")

    # 8) Erreichbar mit Substanz.
    return DimensionVerdict(1, "ok", "erreichbar, Inhalt vorhanden", "html")
