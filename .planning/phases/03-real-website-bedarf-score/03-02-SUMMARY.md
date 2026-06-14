---
phase: 03-real-website-bedarf-score
plan: 02
subsystem: website-bedarf-analyzers
tags: [analyzer, heuristic, dim5, dim6, offline, tdd]
requires: [models.DimensionVerdict, fetch.FetchResult, bs4]
provides: [analyzers.ai_readiness, analyzers.content]
affects: [aggregation-03-03, wiring-03-04]
tech-stack:
  added: []
  patterns: [pure-analyzer, pattern-2-folding, no-html-neutral-guard, defensive-json-parse]
key-files:
  created:
    - lead_analyzer/analyzers/ai_readiness.py
    - lead_analyzer/analyzers/content.py
    - tests/test_ai_readiness.py
    - tests/test_content.py
  modified: []
decisions:
  - "soup=None returns NEUTRAL (ok/n/a, 0 gap-points), never severe — pins 403/no-body != Bedarf 5 invariant"
  - "Dim 5 uses explicit 3-way verdict table; Dim 6 uses Pattern-2 folding"
  - "Copyright freshness derived from datetime.now().year, never hardcoded"
metrics:
  duration: ~12min
  completed: 2026-06-14
  tasks: 4
  files: 4
requirements: [BED-05, BED-06]
---

# Phase 3 Plan 02: Dim 5 KI-Readiness + Dim 6 Inhalt/Aktualität Summary

Two pure, offline heuristic Website-Bedarf analyzers — Dim 5 (structured-markup / answer-engine readiness via JSON-LD + Open Graph + microdata) and Dim 6 (conversion/freshness via contact path, tel/mailto, Impressum, copyright-year bands, legacy-generator) — both honoring the pinned no-HTML-neutral policy that keeps WAF-blocked rows off Bedarf 5.

## What was built

- **`analyzers/ai_readiness.py` (Dim 5, BED-05):** `analyze(soup)` — defensive `json.loads` in try/except (malformed JSON-LD never raises, absence is a signal), inclusive `@type` detection (incl. list `@type`), og:* count, microdata via itemscope/itemtype. Explicit 3-way table: JSON-LD + ≥3 OG → ok; partial → gap; nothing → severe.
- **`analyzers/content.py` (Dim 6, BED-06):** `analyze(fr, soup)` — contact-form/kontakt-link (gap), tel:/mailto: (minor each), Impressum/Datenschutz (gap), copyright bands vs `datetime.now().year` (≥now-1 ok · now-3..now-2 gap · ≤now-4 severe · none minor), legacy `<meta generator>` (gap). Pattern-2 folding (severe → gap ≥1 → ≥2 minor → ok). ReDoS-safe bounded regexes.
- **soup=None guard placed FIRST in both** → `DimensionVerdict(dim, "ok", "nicht bewertbar (kein HTML)", "n/a")`, before any fr.html scan.

## Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | RED Dim 5 tests | test(03-02) | tests/test_ai_readiness.py |
| 2 | GREEN Dim 5 analyzer | feat(03-02) | lead_analyzer/analyzers/ai_readiness.py |
| 3 | RED Dim 6 tests | test(03-02) | tests/test_content.py |
| 4 | GREEN Dim 6 analyzer | feat(03-02) | lead_analyzer/analyzers/content.py |

## Verification

- `tests/test_ai_readiness.py`: 8 passed. `tests/test_content.py`: 10 passed.
- My six in-scope files: 82 passed (64 baseline + 18 new).
- Full suite (excluding orphan `test_technical.py`): 113 passed (includes sibling plan's `test_seo.py` that landed concurrently). No network. No new deps.
- Neither analyzer issues HTTP; `ai_readiness.analyze` has no `fr` param; `content.analyze` reads `fr.html` only for the copyright scan, gated behind the soup=None guard.

## TDD Gate Compliance

Both features followed RED → GREEN: a `test(...)` commit precedes each `feat(...)` commit. No REFACTOR needed.

## Deviations from Plan

None — plan executed exactly as written.

## Notes (out of scope)

- `tests/test_technical.py` causes a collection ImportError (`technical` analyzer not yet implemented — owned by sibling plan 03-01). Pre-existing, untouched. Suite run with `--ignore=tests/test_technical.py`.
- `tests/test_seo.py` appeared mid-execution from a parallel sibling plan; not modified by this plan.

## Self-Check: PASSED

All 4 created files present; all 4 task commits (2 test, 2 feat) confirmed in git log.
