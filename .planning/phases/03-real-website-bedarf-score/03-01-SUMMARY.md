---
phase: 03-real-website-bedarf-score
plan: 01
subsystem: website-bedarf-analyzers
tags: [BED-02, BED-04, dim2, dim4, pure-analyzer, offline, tdd]
requires:
  - lead_analyzer/models.py (DimensionVerdict, FetchResult)
  - tests/conftest.py (make_fetch_result, network block)
provides:
  - lead_analyzer/analyzers/technical.py (Dim 2 Technische Basis)
  - lead_analyzer/analyzers/seo.py (Dim 4 Auffindbarkeit/SEO)
affects:
  - 03-03 aggregation (consumes dim2/dim4 verdicts)
  - 03-04 pipeline wiring
tech-stack:
  added: []   # keine neue Dependency (tldextract bewusst ABGELEHNT)
  patterns:
    - "Pure analyze(fr[, soup]) -> DimensionVerdict, mirror existence.py"
    - "FREE_SUBDOMAIN endswith-Guard (host == d OR host.endswith('.'+d)) statt tldextract"
    - "no-HTML neutral policy fuer Dim 4 (403 != Bedarf 5 by construction)"
key-files:
  created:
    - lead_analyzer/analyzers/technical.py
    - lead_analyzer/analyzers/seo.py
    - tests/test_technical.py
    - tests/test_seo.py
  modified: []
decisions:
  - "Dim 2 misst auch ohne Body (html=None): HTTPS/SSL/Host stammen aus FetchResult, kein Neutral-Kurzschluss."
  - "Dim 4 gibt NEUTRAL (level ok, source n/a, 0 Gap-Punkte) bei soup=None, damit WAF-403 nicht auf Bedarf 5 kippt."
  - "robots.txt / sitemap.xml DEFERRED (extra HTTP + Cache, Phase 5/6); Dim 4 misst nur Einzelseiten-noindex (Meta + X-Robots-Tag)."
metrics:
  duration: ~10min
  completed: 2026-06-14
  tasks: 4
  files: 4
---

# Phase 3 Plan 01: Dim 2 (Technische Basis) + Dim 4 (SEO/Auffindbarkeit) Summary

Zwei reine, offline testbare Website-Bedarf-Analyzer: Dim 2 misst HTTPS + gültiges SSL + eigene-vs-Gratis-Subdomain (dependency-frei via FREE_SUBDOMAIN endswith-Set), Dim 4 misst Einzelseiten-Auffindbarkeit (Title/Meta-Description/H1/Canonical/lang/noindex via Meta+Header) über eine vor-geparste BeautifulSoup. Beide folgen dem `existence.py`-Stil und dem Pattern-2-Faltungsregel.

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | RED: tests/test_technical.py (BED-02) | 8fce9f8 | tests/test_technical.py |
| 2 | GREEN: technical.py (Dim 2) | 44b1360 | lead_analyzer/analyzers/technical.py |
| 3 | RED: tests/test_seo.py (BED-04) | 4c41edd | tests/test_seo.py |
| 4 | GREEN: seo.py (Dim 4) | a11de6f | lead_analyzer/analyzers/seo.py |

## Implementation notes

- **Dim 2 (technical.py):** Reine `analyze(fr)`. Drei harte Signale (kein "minor"-Tier): `scheme == "http"` → severe "kein HTTPS"; `fr.ssl_ok is False` → severe "ungültiges SSL-Zertifikat"; Gratis-Subdomain via `_is_free_subdomain(host)` → severe. Der endswith-Guard (`host == d or host.endswith("."+d)`) verhindert, dass `evilwix.com` auf `wix.com` matcht. www wird gestrippt. Leeres Schema (None/leeres final_url) wird NICHT als http geflaggt. **Bewusst KEIN HTML-Guard** — Dim 2 bleibt bei `html=None` (WAF-403) voll messbar.
- **Dim 4 (seo.py):** Reine `analyze(fr, soup)`, baut KEINE soup selbst (parse-once-Vertrag). noindex via Meta-Robots (`^robots$`-Regex) ODER X-Robots-Tag-Header (case-insensitive Key-Lookup) → severe. Pflicht (gap bei Fehlen): Title, Meta-Description, ≥1 H1. minor: Title-/Desc-Länge, mehrere H1, kein Canonical, kein html-lang. Pattern-2: any severe → severe; ≥1 gap ODER ≥2 minor → gap; sonst ok.

## no-HTML neutral policy (pinned)

`seo.analyze(fr, None)` → `DimensionVerdict(4, "ok", "nicht bewertbar (kein HTML)", "n/a")` — 0 Gap-Punkte, NICHT severe/gap. Damit kippt ein reachable-but-no-body Row (403/406/429, leerer Body) nicht auf Bedarf 5. `source == "n/a"` macht das Neutral-Verdict von einem echten "ok" unterscheidbar. Dim 2 bleibt im selben Fall voll gemessen → die "403/blocked != Bedarf 5"-Invariante hält by construction.

## DEFERRED

- **robots.txt / sitemap.xml** sind explizit ausgelassen (sie bräuchten einen zusätzlichen HTTP-Abruf + Cache → Phase 5/6). Dim 4 misst hier nur Einzelseiten-Indexierbarkeit (Meta-Robots + X-Robots-Tag-Header). AC11 bleibt erfüllt: Dimensionen 1–4 werden real gemessen.

## Deviations from Plan

None - plan executed exactly as written. (Out-of-scope: sibling-plan RED commits 03-02/03-03 — test_ai_readiness.py, test_scoring_bedarf.py, test_content.py — fail/error by design because their analyzers don't exist yet; not part of this plan's scope, untouched.)

## TDD Gate Compliance

Beide Features durchliefen RED→GREEN: `test(03-01)` vor `feat(03-01)` für Dim 2 (8fce9f8 → 44b1360) und Dim 4 (4c41edd → a11de6f). Kein REFACTOR-Schritt nötig.

## Verification

- `tests/test_technical.py` (11) + `tests/test_seo.py` (10) + `tests/test_existence.py` (13) GREEN.
- Voller in-scope Lauf (sibling-RED-Dateien ausgeschlossen): **90 passed**, kein Netz benutzt (conftest autouse-Block hielt).
- Purity: weder `technical.py` noch `seo.py` importieren `requests` oder bauen eine eigene HTTP-Verbindung; `seo.py` baut keine BeautifulSoup (erhält soup).

## Self-Check: PASSED

- lead_analyzer/analyzers/technical.py — FOUND
- lead_analyzer/analyzers/seo.py — FOUND
- tests/test_technical.py — FOUND
- tests/test_seo.py — FOUND
- Commits 8fce9f8, 44b1360, 4c41edd, a11de6f — FOUND
