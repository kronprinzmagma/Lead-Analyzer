"""Dimension 2 — Technische Basis (rein, offline).

`analyze(fr)` wandelt ein `FetchResult` in einen `DimensionVerdict(dim=2, ...)`.
Kein I/O, KEIN HTML nötig: die drei Signale (HTTPS, gültiges SSL, eigene vs.
Gratis-Subdomain) stammen aus `final_url`/`url`-Schema, `ssl_ok` und dem Host —
alle auch bei WAF-blockierten Zeilen (html=None) vorhanden. Daher gibt Dim 2
KEINEN Neutral-Kurzschluss bei fehlendem Body, sondern misst weiter.

Dim 2 hat KEINE "minor"-Stufe — HTTPS/SSL/eigene-Domain sind harte Signale:
jedes feuernde Signal -> "severe"; sonst -> "ok". Der "keine Website"-Fall wird
upstream von Dim 1 (existence) behandelt.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from ..models import DimensionVerdict


# Gratis-/Baukasten-Subdomains: eigene Domain fehlt -> klarer Bedarf.
# Dependency-frei (tldextract bewusst ABGELEHNT): Match via host == d ODER
# host endswith "." + d, sodass z.B. evilwix.com NICHT auf wix.com matcht.
# [CITED: FEATURES.md Dim-2]
FREE_SUBDOMAIN = {
    "wixsite.com", "wix.com", "editorx.io", "jimdosite.com", "jimdofree.com",
    "business.site", "wordpress.com", "weebly.com", "webnode.page", "webnode.com",
    "squarespace.com", "square.site", "webflow.io", "github.io", "myshopify.com",
    "strikingly.com", "sitew.com", "webador.ch", "webador.com", "page.link",
    "blogspot.com", "yolasite.com", "ucraft.site", "mystrikingly.com",
}


def _is_free_subdomain(host: str) -> str | None:
    """Liefert die getroffene Gratis-Domain oder None (endswith-Guard, www-Strip)."""
    host = host.lower().removeprefix("www.")
    for d in FREE_SUBDOMAIN:
        if host == d or host.endswith("." + d):
            return d
    return None


def analyze(fr) -> DimensionVerdict:
    """Reiner Dimension-2-Befund über ein `FetchResult` (ohne HTML messbar)."""
    parts = urlsplit(fr.final_url or fr.url or "")
    host = parts.netloc.lower().removeprefix("www.")
    scheme = parts.scheme.lower()

    notes: list[str] = []

    # 1) HTTPS fehlt (leeres Schema NICHT fälschlich flaggen -> nur explizit http).
    if scheme == "http":
        notes.append("kein HTTPS")

    # 2) Ungültiges SSL-Zertifikat (fetch fiel auf verify=False zurück).
    if fr.ssl_ok is False:
        notes.append("ungültiges SSL-Zertifikat")

    # 3) Gratis-/Baukasten-Subdomain statt eigener Domain.
    d = _is_free_subdomain(host)
    if d:
        notes.append(f"Gratis-Subdomain {d}, keine eigene Domain")

    if notes:
        return DimensionVerdict(2, "severe", "; ".join(notes), "html")
    return DimensionVerdict(2, "ok", "eigene Domain, HTTPS, gültiges SSL", "html")
