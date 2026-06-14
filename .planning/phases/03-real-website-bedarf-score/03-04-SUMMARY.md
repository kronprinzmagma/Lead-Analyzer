---
phase: 03-real-website-bedarf-score
plan: 04
subsystem: api
tags: [pipeline, beautifulsoup, scoring, aggregation, parse-once, integration]

requires:
  - phase: 03-01
    provides: technical (Dim2), seo (Dim4), reasons.build, DIM3_PLACEHOLDER
  - phase: 03-02
    provides: ai_readiness (Dim5), content (Dim6)
  - phase: 03-03
    provides: scoring.bedarf (6-Dim-Aggregation)
  - phase: 02
    provides: existence (Dim1), fetch, RowResult/DimensionVerdict
provides:
  - "analyze_row mit voller 6-Dimensionen-Bewertung (parse-once)"
  - "Begründungsspalte aus reasons.build (NACH-01) end-to-end"
  - "403/Block != Bedarf 5 Invariante by construction über den Pipeline-Pfad"
affects: [04-zahlungskraeftigkeit, 06-pagespeed]

tech-stack:
  added: []
  patterns:
    - "fetch-once-parse-many: eine BeautifulSoup pro Zeile, geteilt an Dim 1/4/5/6"
    - "existence.analyze kopiert die soup vor destruktivem decompose() (geteilte soup bleibt intakt)"

key-files:
  created:
    - tests/test_pipeline_bedarf.py
  modified:
    - lead_analyzer/pipeline.py
    - lead_analyzer/analyzers/existence.py
    - lead_analyzer/scoring.py
    - tests/test_pipeline_dim1.py

key-decisions:
  - "existence.analyze kopiert die übergebene soup vor decompose(), damit die geteilte Pipeline-soup für Dim 4/5/6 intakt bleibt"
  - "403-no-body Bedarf-Wert dokumentiert/asserted als 2 (war provisorisch 3); !=5-Invariante bleibt explizit"
  - "bedarf_from_dim1 bleibt erhalten (deprecated) für Phase-2-Unit-Tests"

patterns-established:
  - "parse-once: BeautifulSoup wird genau einmal pro Zeile gebaut und durchgereicht"
  - "Single source of truth: RowResult.reason == reasons.build(verdicts)"

requirements-completed: [BED-02, BED-04, BED-05, BED-06, BED-07, BED-08, NACH-01]

duration: 4min
completed: 2026-06-14
---

# Phase 3 Plan 04: Pipeline-Verdrahtung (6-Dimensionen-Bedarf) Summary

**analyze_row parst HTML genau einmal und führt alle sechs Bedarf-Dimensionen (existence/technical/dim3-Platzhalter/seo/ai_readiness/content) über scoring.bedarf zusammen; die Begründungsspalte kommt aus reasons.build — end-to-end über data/sample_input.xlsx lauffähig.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-14T14:14:56Z
- **Completed:** 2026-06-14T14:18:53Z
- **Tasks:** 4
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- Voller 6-Dimensionen-Score in analyze_row verdrahtet (BED-02/04/05/06/07/08).
- parse-once: genau eine BeautifulSoup pro Zeile, geteilt an Dim 1/4/5/6 (grep `BeautifulSoup(` == 1 in pipeline.py).
- Begründungsspalte aus reasons.build (NACH-01); RowResult.reason == reasons.build(verdicts).
- 403/Block != Bedarf 5 by construction; modern→1, broken→5, http-only>1; Richtungs-Gradient nicht-fallend.
- Live-Lauf über data/sample_input.xlsx (42 Zeilen) erzeugt sinnvolle Verteilung über das ganze Spektrum 1–5.

## Task Commits

1. **Task 1: existence.analyze optionale soup (parse-once)** - `a44e853` (refactor)
2. **Task 2: RED 6-Dim-Integrationstests** - `25771dc` (test)
3. **Task 3+4: GREEN rewire analyze_row + dim1-Reconciliation + Gradient** - `61c69ab` (feat)

## Files Created/Modified
- `lead_analyzer/pipeline.py` - analyze_row baut eine soup, ruft alle 6 Dimensionen, aggregiert via scoring.bedarf, Begründung via reasons.build; Per-Row-Boundary + leere-URL-Kurzschluss erhalten.
- `lead_analyzer/analyzers/existence.py` - `analyze(fr, soup=None)`; nutzt vor-geparste soup (kopiert vor decompose()), backward compatible.
- `lead_analyzer/scoring.py` - bedarf_from_dim1 als deprecated markiert (für Phase-2-Unit-Tests erhalten).
- `tests/test_pipeline_bedarf.py` - Offline-Integration: 6 Verdicts, modern→1, broken→5, 403-no-body !=5 und ==2, http-only>1, reason threaded, zahl-Platzhalter, Boundary, Richtungs-Gradient.
- `tests/test_pipeline_dim1.py` - reconciled: reason-Substring statt startswith, 403→2, thin→4.

## Decisions Made
- existence.analyze kopiert die übergebene soup vor dem destruktiven `decompose()` (BeautifulSoup(str(base))), damit die geteilte Pipeline-soup für Dim 4/5/6 unverändert bleibt. Verhalten von Dim 1 identisch (alle 13 existence-Tests grün).
- 403-no-body Bedarf-Wert dokumentiert als **2** (clean-https WAF: Dim1 gap + Dim2 ok + Dim4/5/6 neutral → G=1 → Band 2). In beiden Test-Dateien identisch asserted; `!= 5` bleibt explizit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Geteilte soup wurde durch existence.decompose() zerstört**
- **Found during:** Task 1 (existence-Refactor)
- **Issue:** Würde existence die geteilte Pipeline-soup direkt nutzen, würde sein `decompose()` der `script/style/nav/footer`-Tags den Baum verändern, bevor Dim 4/5/6 ihn lesen — die nachgelagerten Dimensionen sähen ein verstümmeltes Dokument.
- **Fix:** existence kopiert die soup (`BeautifulSoup(str(base), "html.parser")`) vor decompose(); der geteilte Baum bleibt intakt.
- **Files modified:** lead_analyzer/analyzers/existence.py
- **Verification:** Alle 13 existence-Tests + alle Dim 4/5/6-Tests + die 6-Dim-Integration grün.
- **Committed in:** a44e853

---

**Total deviations:** 1 auto-fixed (1 Bug)
**Impact on plan:** Notwendig für die Korrektheit des parse-once-Vertrags. Kein Scope-Creep.

## Reconciliation Notes (für Phase-Historie)
- **reason-Text:** `test_dead_unreachable_is_bedarf_5` von `.startswith("nicht erreichbar")` auf Substring `"nicht erreichbar" in reason` umgestellt — RowResult.reason kommt jetzt aus reasons.build (kompakte "Dim… → Bedarf N"-Form). `"blockiert"` bleibt Substring für die 403-Zeile.
- **403-no-body Wert:** provisorisch 3 → dokumentiert/asserted **2** (clean-https-WAF); `!= 5`-Invariante beibehalten; identischer Wert in test_pipeline_bedarf.py und test_pipeline_dim1.py.
- **thin-Zeile:** provisorisch 3 → **4** (Dim1 gap + Dim4 gap + Dim5 severe + Dim6 gap). Test umbenannt `test_reachable_thin_is_3` → `test_reachable_thin_is_4`.
- **social-only:** unverändert 4 (severe-not-dead bleibt im 6-Dim-Pfad 4).
- bedarf_from_dim1-Unit-Tests unverändert (testen scoring direkt).

## Sample-Lauf (live, best-effort)
`python run.py data/sample_input.xlsx -o output/phase3_check.xlsx` → 42 Zeilen.
Bedarf-Verteilung: {1: 3, 2: 12, 3: 15, 4: 10, 5: 2}. Beispiele:
- B5 — Kiosk am Lindenplatz (leere URL) → "keine Website"
- B5 — Nähatelier Sutter (kaputte URL) → "Dim1 schwere Lücke (nicht erreichbar…); Dim2 schwere Lücke…"
- B4 — Feusi Malergeschäft → "Dim1 Lücke (dünner Inhalt); Dim4 Lücke (keine Meta-Description; 0× H1; kein Canonical)…"
- B1 (3×) — moderne Sites über alle Dimensionen.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Website-Bedarf (Dimension 1, 2, 4, 5, 6 + Dim-3-Platzhalter) end-to-end fertig.
- Phase 4 (Zahlungskräftigkeit) ersetzt `_zahl_placeholder`; Phase 6 ersetzt DIM3_PLACEHOLDER durch echten PageSpeed-Befund — beide Hooks stehen.

## Self-Check: PASSED

---
*Phase: 03-real-website-bedarf-score*
*Completed: 2026-06-14*
