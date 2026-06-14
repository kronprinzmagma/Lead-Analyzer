---
phase: 6
slug: optional-pagespeed-rate-limiting
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 6 — Validation Strategy

> Derived from 06-RESEARCH.md. Fully offline: PSI client mocked, injected sleep (no real backoff waits), no real key. PSI default OFF without key → offline output byte-identical to Phase 5 for viewport-present rows. A genuinely viewport-absent row now scores Dim 3 = gap (real BED-03 behavior) and its Bedarf may legitimately change vs Phase 5; any such single change is cited as BED-03.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Quick run** | `python -m pytest tests/ -q` |
| **Network policy** | autouse conftest fixture fails un-mocked requests; PSI tests monkeypatch requests.get |
| **Cache** | PSI cached via namespaced key cache.key_for(["pagespeed-v1","mobile",url]); tests use tmp cache dir |

## Per-Requirement Verification Map

| Requirement | Observable validation | Test type | Status |
|---|---|---|---|
| **BED-03** (Dim 3: viewport always + PSI when available; degrade with note) | performance.analyze(fr, None) → viewport-only verdict (present→ok, absent→gap); with ps_result → Lighthouse perf score thresholds (≥0.9 ok / 0.5-0.89 gap / <0.5 severe) + LCP/CLS/TBT; PSI error/None → viewport heuristic + "(PageSpeed übersprungen/Fehler)" note, NEVER scored slow. | unit | Pending |
| **PERF-02** (client availability, backoff, budget, Retry-After, --no-pagespeed — AC8) | is_available() (key present); score() returns None on RequestException/non-200/429-after-retries/malformed/budget-exhausted (never raises); semaphore caps concurrent PSI; backoff honors Retry-After (injected sleep); per-run budget cap; --no-pagespeed forces off. | unit (mocked) | Pending |
| **Monotonicity preserved** | replacing DIM3_PLACEHOLDER with real verdict keeps scoring.bedarf monotonic; viewport-present default path → Dim 3 ok (0 pts) → 177 tests unchanged (viewport-absent fixtures may shift one assertion, cited as BED-03). | unit + regression | Pending |
| **AC9 .env** | stdlib .env loader: KEY=VALUE, ignore comments/blank, strip quotes, os.environ.setdefault (never override), never raise on missing file. | unit | Pending |

## Offline Integration Check

`python run.py data/sample_input.xlsx -o out.xlsx` (no key) → PSI auto-OFF, Dim 3 = viewport heuristic. Output byte-identical to Phase 5 for viewport-present fixtures; a genuinely viewport-absent row scores Dim 3 = gap (real BED-03) and may legitimately shift Bedarf — each such change cited as BED-03. With a (mocked) key + PSI on, Dim 3 refines but run still completes; a forced PSI 429/timeout never aborts and never scores a site as slow.

## Wave 0 — Test File Gaps

- tests/test_performance.py (new) — viewport-only verdict, PSI-refined verdict thresholds, PSI-error-not-slow golden test.
- tests/test_pagespeed_client.py (new) — mocked 200/429+Retry-After/timeout/malformed → None; budget; semaphore; injected sleep.
- tests/test_env_loader.py (new) — KEY=VALUE parse, comments, quotes, setdefault no-override, missing file.
- extend tests/test_scoring_bedarf.py / test_pipeline — Dim 3 real verdict in aggregation, monotonic.
