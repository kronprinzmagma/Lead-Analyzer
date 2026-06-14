---
phase: 02-fetch-existence-dim-1-robustness
plan: 02
subsystem: fetch + pipeline (Dimension-1 wiring)
tags: [fetch, http, robustness, dimension-1, offline-testable]
requires: [02-01]
provides:
  - "lead_analyzer.fetch.fetch(candidates, config) -> FetchResult (never raises)"
  - "lead_analyzer.scoring.bedarf_from_dim1(verdict) -> int (dead->5 override)"
  - "real analyze_row wired: normalize -> fetch -> existence.analyze -> dead->5, per-row boundary"
affects: [pipeline, scoring, fetch]
tech-stack:
  added: []
  patterns:
    - "single network seam (fetch) — tests monkeypatch requests.Session.get; everything else pure/offline"
    - "SSL-as-signal: verify=True first, on SSLError refetch verify=False, ssl_ok=False, body still read"
    - "stream=True + 2 MB byte cap + errors='replace' decode (DoS + encoding robustness)"
    - "bare except Exception per-row boundary so one bad row never aborts the run"
key-files:
  created:
    - tests/test_pipeline_dim1.py
  modified:
    - lead_analyzer/fetch.py
    - lead_analyzer/scoring.py
    - lead_analyzer/pipeline.py
    - tests/test_fetch.py
decisions:
  - "Provisional non-dead Bedarf: severe-not-dead (Social-only)=4, gap/ok=3 (Open Question 1; Phase-3 aggregation replaces this)"
  - "InsecureRequestWarning suppressed only on the scoped verify=False refetch path, never globally"
  - "403/406/429 -> neutral Bedarf 3 'blockiert', NOT 5 (WAF block must not become a top lead)"
metrics:
  duration: "~14 min"
  completed: 2026-06-14
  tasks: 3
  files-changed: 4
  tests: "61 passed (36 prior + 25 new Phase-2)"
---

# Phase 2 Plan 02: Fetch + Dimension-1 Wiring Summary

Never-raising `fetch()` network seam (hard timeout, browser/de-CH headers, redirect cap, 2 MB stream cap, SSL-as-signal) plus a real `analyze_row` that wires normalize -> fetch -> existence.analyze with a dead->Bedarf-5 override inside a per-row exception boundary; `zahl` stays on the Phase-1 placeholder.

## What Was Built

- **`fetch.fetch(candidates, config)`** (appended to `lead_analyzer/fetch.py`): the single network boundary. `timeout=(config.timeout_connect, config.timeout_read)`, browser UA + `Accept-Language: de-CH`, `session.max_redirects=10`, `stream=True` with a 2 MB byte cap, declared->apparent encoding decode with `errors="replace"`. On `SSLError` it refetches `verify=False` (ssl_ok=False, body still read) with the `InsecureRequestWarning` suppressed scoped to that path. Every requests exception maps to a note; a bare `except Exception` guarantees it never raises. A real HTTP response (any status) stops variant probing.
- **`scoring.bedarf_from_dim1(verdict)`**: dead causes (reason starts "nicht erreichbar" / "geparkt") -> 5; severe-not-dead -> 4; gap/ok -> 3 (all clamped).
- **`pipeline.analyze_row`** rewritten: empty/None URL -> Bedarf 5 "keine Website" with NO fetch; else fetch -> existence.analyze -> bedarf_from_dim1; wrapped in a bare `except Exception` returning a degraded `RowResult(bedarf=5, reason="Fehler: ...")`. Signature and `run()` unchanged. `zahl` via `_zahl_placeholder()`.
- **Tests**: `tests/test_fetch.py` gained 11 fetch() tests (request shape, SSL signal, timeout, connection error, too-many-redirects, encoding fallback, byte cap, 4xx-stops-probing, never-raises, empty candidates, clean 200). `tests/test_pipeline_dim1.py` (new, 14 tests) covers bedarf_from_dim1 mapping, empty-URL-no-network, dead->5, parked->5, 403-neutral, social=4, thin=3, zahl-placeholder, row boundary, run-continues-after-bad-row, and the offline sample integration.

## Verification

- Full suite: **61 passed** (36 prior Phase-1 + Phase-2; 0 failures). Network block from conftest intact — no test performs a real request.
- `test_sample_offline`: real `data/sample_input.xlsx`, `fetch.fetch` monkeypatched; `len(out)==len(in)`, every bedarf int in [1,5], Kiosk (empty URL) and Nähatelier (broken `htp://naehatelier-sutter`) rows both == 5.
- Real e2e smoke run (limit=3, live network) completed without crashing and produced real Dim-1 verdicts.
- `grep -c "except Exception" pipeline.py` == 1; `grep -c "def fetch" fetch.py` == 1; fetch uses `config.timeout_connect`.

## Deviations from Plan

None — plan executed as written. The provisional non-dead Bedarf values (Social-only=4, gap/ok=3) follow RESEARCH Open Question 1's recommendation and are explicitly provisional until Phase-3 aggregation.

## Known Stubs

- `zahl` is intentionally on the Phase-1 placeholder (constant 3) — Phase 4 (Zahlungskräftigkeit) owns it; documented in the plan and CLAUDE.md scope.
- Non-dead Bedarf is provisional (4/3) pending Phase-3 six-dimension aggregation. Not a blocker for Phase 2's gated scope (Dimension 1 + robustness).
- Thin-content threshold (300 words) is the RESEARCH A1 heuristic; many real Swiss SME homepages currently read as "dünner Inhalt" -> 3. Tunable in Phase 3; does not affect the deterministic edge-case->5 behavior.

## Commits

- `7948bd6` test(02-02): add failing fetch() request-shape/ssl/timeout/encoding tests
- `1b7f99b` feat(02-02): never-raising fetch() network seam with SSL-as-signal
- `ec9c17d` test(02-02): add failing analyze_row dead->5 / ROB-01/03 + sample-offline tests
- `6cbc676` feat(02-02): wire analyze_row dim-1 with dead->5 override + per-row boundary

## Self-Check: PASSED

All created/modified files present; all 4 task commits found in git history; full suite 61 passed.
