---
phase: 06-optional-pagespeed-rate-limiting
plan: 05
subsystem: pipeline
tags: [pipeline, dim3, pagespeed, wiring, monotonicity, byte-identical, threadpool, bed-03]

requires:
  - phase: 06-optional-pagespeed-rate-limiting (Plan 03)
    provides: performance.analyze(fr, soup, ps_result) -> DimensionVerdict(dim=3)
  - phase: 06-optional-pagespeed-rate-limiting (Plan 04)
    provides: PageSpeedClient.from_config / is_available / score(url) -> PsResult | None
  - phase: 03 (six-dimension wiring)
    provides: analyze_row verdict list, scoring.bedarf, reasons.build
provides:
  - Dim-3 end-to-end wiring in analyze_row (performance.analyze replaces scoring.DIM3_PLACEHOLDER)
  - one shared PageSpeedClient per run (single semaphore + budget) threaded through pool.submit
  - offline byte-identical regression test (no key, varying workers) guarding monotonicity
affects: [phase verification, BED-03 capability complete]

tech-stack:
  added: []
  patterns:
    - "Degradation-contract wiring: ps_result gated on client present + is_available() + fr.ok + fr.html"
    - "Single-client-per-run invariant (from_config called once, never per row) for shared budget/semaphore"
    - "Offline default byte-identical to prior phase for viewport-present rows (Dim 3 ok = 0 gap-points)"

key-files:
  created: []
  modified:
    - lead_analyzer/pipeline.py
    - tests/test_pipeline_bedarf.py
    - tests/test_pipeline_dim1.py

key-decisions:
  - "analyze_row gains ps_client=None keyword -> direct-call tests stay backward compatible (ps_result None -> viewport heuristic)"
  - "PSI call gated on fr.ok and fr.html (T-06-12): dead/blocked rows never spend budget; Dim 1 already drives those"
  - "from_config built ONCE in run() before the pool, passed via pool.submit (PERF-02/AC8) -> test_one_client_per_run GREEN"
  - "scoring.DIM3_PLACEHOLDER stays defined (other code may reference it); only its USE in analyze_row was replaced"
  - "Scoring bands UNCHANGED; all assertion changes justified by genuinely viewport-ABSENT fixtures (grep-confirmed)"

patterns-established:
  - "Pattern: byte-identical offline regression — run() with a DIM3_PLACEHOLDER override as baseline vs. real offline path"
  - "Pattern: mechanical grep gate (meta name=\"viewport\" count == 0) before editing any Bedarf assertion"

requirements-completed: [BED-03, PERF-02]

duration: ~15min
completed: 2026-06-14
---

# Phase 6 Plan 05: Pipeline Wiring (Dim 3) Summary

End-to-end Dimension-3 wiring: `analyze_row` now builds the Dim-3 verdict from
`performance.analyze(fr, soup, ps_result)` (replacing the static `scoring.DIM3_PLACEHOLDER`),
`run()` constructs exactly one shared `PageSpeedClient` per run, and the keyless offline path
stays byte-identical to Phase 5 for viewport-present rows.

## What Was Built

- **analyze_row** gains `ps_client=None` (keyword). After parse-once `soup`, a gated block:
  `if ps_client is not None and ps_client.is_available() and fr.ok and fr.html: ps_result = ps_client.score(fr.final_url or fr.url)` — otherwise `None`. The Dim-3 slot in the verdict list is now `performance.analyze(fr, soup, ps_result)`. The empty-URL early-return and the except-boundary paths are untouched (no fetch -> no PSI).
- **run()** builds `ps_client = PageSpeedClient.from_config(config)` ONCE before the ThreadPoolExecutor and passes it into every `pool.submit(analyze_row, r, url_col, config, ps_client)`. One instance -> shared semaphore + budget across all worker threads. `from_config` returns `None` without `use_pagespeed`/key -> offline default unchanged.
- **Offline byte-identical regression test** (`test_offline_output_byte_identical_to_placeholder`): runs `run()` over a 3-row viewport-present CSV with no key; a baseline run patches `performance.analyze` to return `DIM3_PLACEHOLDER` (Phase-5 behavior), then asserts the real offline output is byte-equal at workers=1 and workers=8.

## Verification

- Full suite: **200 passed** (198 prior + the previously-RED `test_one_client_per_run` now GREEN + new byte-identical test).
- `test_no_pagespeed_flag` and `test_one_client_per_run` both GREEN (from_config called exactly once per run).
- Live smoke: `python run.py data/sample_input.xlsx -o output/phase6_check.xlsx` (no key -> PSI off) processed **42 rows** offline-safe, exit 0. PSI-refined reasons = 0 (confirmed offline); Dim-3 fragments observed: a broken `htp://` row -> Dim3 gap `kein viewport-meta (PageSpeed übersprungen/Fehler)` Bedarf 5; `https://www.kmu-trex.ch/` -> Dim3 ok (viewport present, not listed in Begründung; 0 gap-points = Phase-5-identical) Bedarf 4.

## Deviations from Plan

### Justified test assertion updates (Task 2 — BED-03, mechanical grep gate)

All changed fixtures were confirmed viewport-ABSENT via `grep -ic 'meta name="viewport"'` returning **0** before any edit. No scoring band was changed; no analyzer threshold was weakened.

**1. [Rule 1 - behavior surfacing] `test_six_verdicts_wired` Dim3 ok -> gap**
- **Fixture:** default `make_fetch_result` HTML (`<html><head><title>Beispiel</title>...`). Grep = 0 (no viewport).
- **Change:** assertion `dim3.level == "ok"` -> `"gap"`; comment cites BED-03 + grep result.
- **File:** tests/test_pipeline_bedarf.py · **Commit:** 34de199

**2. [Rule 1] `test_block_403_no_body_is_not_5_and_is_2` -> Bedarf 3**
- **Fixture:** 403 with `html=None` -> `soup` is None -> no viewport (genuinely unobtainable). Grep N/A (no body).
- **Change:** `== 2` -> `== 3` (Dim1 gap + Dim3 gap -> G=2 -> band 3). The load-bearing `!= 5` invariant preserved. Comment cites BED-03.
- **File:** tests/test_pipeline_bedarf.py · **Commit:** 34de199

**3. [Rule 1] `test_block_403_is_neutral_not_5` (dim1) -> Bedarf 3**
- Same 403/no-body case as #2, mirrored in the dim1 suite. `== 2` -> `== 3`, BED-03 cited.
- **File:** tests/test_pipeline_dim1.py · **Commit:** 34de199

**4. [Rule 1] `_MODERN_HTML` fixture given a viewport-meta**
- **Fixture:** the "fully modern site -> Bedarf 1" fixture lacked a viewport tag (grep = 0). A genuinely modern site HAS a viewport; the fixture predated the real Dim 3.
- **Change:** added `<meta name="viewport" content="width=device-width, initial-scale=1">` so the fixture truly satisfies all six dims; `test_modern_site_is_bedarf_1` keeps asserting Bedarf 1 (its real intent). Bands untouched.
- **File:** tests/test_pipeline_bedarf.py · **Commit:** 34de199

**5. [Rule 1] `test_social_only_high_but_not_5` (dim1) fixture given a viewport-meta**
- **Fixture:** `<html><body>Profil</body></html>` (grep = 0). This test asserts the Dim-1 concern (social-only = severe but NOT dead-5). An extra Dim-3 gap on the already-thin page tipped G to band 5, colliding with the test's intent.
- **Change:** added a viewport-meta so the unrelated Dim-3 gap does not overlay the Dim-1 behavior; documented value `== 4` restored. Bands untouched.
- **File:** tests/test_pipeline_dim1.py · **Commit:** 34de199

No viewport-PRESENT fixture failed (which would have indicated a wiring bug). No `scoring.py` edits.

## Threat Surface

No new trust-boundary surface introduced. The wiring honors the plan's threat register:
T-06-12 (gate PSI on `fr.ok`/`fr.html`), T-06-13 (viewport-present default = identical Bedarf; byte-identical regression test), T-06-14 (score() returns None, per-row boundary intact), T-06-15 (single client per run; `test_one_client_per_run` fails any per-row refactor).

## Self-Check: PASSED

- lead_analyzer/pipeline.py — FOUND (contains `performance.analyze` and `from_config`)
- tests/test_pipeline_bedarf.py, tests/test_pipeline_dim1.py — FOUND
- Commit 34de199 — FOUND in git log
