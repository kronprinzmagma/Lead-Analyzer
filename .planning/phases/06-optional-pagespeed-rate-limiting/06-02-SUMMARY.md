---
phase: 06-optional-pagespeed-rate-limiting
plan: 02
subsystem: config
tags: [tdd, green, env-loader, psresult, cli, no-pagespeed, degradation-contract]
requires: [01]
provides: [load_dotenv, PsResult, no-pagespeed-flag, pagespeed-config-fields]
affects: [lead_analyzer/config.py, lead_analyzer/models.py, lead_analyzer/cli.py]
tech-stack:
  added: []
  patterns: [stdlib-dotenv-setdefault, json-serializable-dataclass, single-call-site-env-load]
key-files:
  created: []
  modified: [lead_analyzer/config.py, lead_analyzer/models.py, lead_analyzer/cli.py]
decisions:
  - "load_dotenv uses os.environ.setdefault (real exported var always wins, T-06-03) and try/except OSError (malformed file never crashes startup, T-06-04)."
  - "use_pagespeed default left at True in Config; the no-key OFF policy lives in from_config (Plan 04). --no-pagespeed forces use_pagespeed=False at the CLI regardless of key."
metrics:
  duration: ~8m
  completed: 2026-06-14
---

# Phase 6 Plan 02: .env Loader + PsResult + --no-pagespeed Summary

Stdlib `.env` loader (zero new deps, AC9), the JSON-serializable `PsResult` dataclass, PSI tuning fields on Config, and the `--no-pagespeed` CLI flag with a single `load_dotenv()` call before Config construction — the degradation-contract gate that Plans 03/04 build on.

## What was built

- **lead_analyzer/config.py** — `load_dotenv(path=".env")`: parses KEY=VALUE, ignores comments/blank/no-`=` lines, strips surrounding quotes, `setdefault` (no override), OSError-safe (never raises). Added Config fields `pagespeed_concurrency: int = 2`, `pagespeed_budget: int = 400`.
- **lead_analyzer/models.py** — `PsResult` dataclass (`perf_score/lcp_ms/cls/tbt_ms` float|None, `ok` bool); JSON-native fields round-trip through cache via `__dict__`; failure is signaled by `None` (not `ok=False`).
- **lead_analyzer/cli.py** — `--no-pagespeed` (store_true, German help); `load_dotenv()` as first statement in `main()`; `use_pagespeed=not args.no_pagespeed` wired into Config.

## Test impact

- `tests/test_env_loader.py`: 4/4 GREEN (was RED in 06-01).
- PsResult round-trip verified: `PsResult(**PsResult(perf_score=0.5).__dict__) == original`.
- `--no-pagespeed` parses to True.
- Full suite: 181 passed (177 original unregressed + 4 env_loader). RED-by-design remaining: test_performance.py + test_pagespeed_client.py (collection errors, await 06-03/06-04) and test_pipeline_bedarf.py::{test_no_pagespeed_flag, test_one_client_per_run} (fail on missing clients package, await 06-04/06-05).

## Deviations from Plan

None - plan executed as written.

## Self-Check: PASSED

- load_dotenv importable from lead_analyzer.config; PsResult from lead_analyzer.models (FOUND).
- Commits d80c804, c2f3a6a exist in git log (FOUND).
- env_loader tests green; existing 177 unregressed.
