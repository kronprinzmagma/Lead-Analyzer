---
phase: 08-company-research-zefix-for-zahlungskr-ftigkeit
plan: "01"
subsystem: zefix-client
tags: [zefix, http-client, rate-limiting, swiss-commercial-register, tdd]
dependency_graph:
  requires: []
  provides: [lead_analyzer/clients/zefix.py, ZefixFacts dataclass, Config zefix fields]
  affects: [lead_analyzer/models.py, lead_analyzer/config.py]
tech_stack:
  added: []
  patterns: [credential-gated client, budget and semaphore concurrency cap, cache-aside with negative hits, injected sleep for tests]
key_files:
  created:
    - lead_analyzer/clients/zefix.py
    - tests/test_zefix_client.py
  modified:
    - lead_analyzer/models.py
    - lead_analyzer/config.py
decisions:
  - "Mirror pagespeed.py structure verbatim — _Budget, _backoff_delay, _parse_retry_after copied with future-refactor comment"
  - "Use ehraid integer to construct source_url, never echo URL field from response (T-08-02)"
  - "Negative hits (_miss: True) cached; transient errors (timeout/non-200) NOT cached"
  - "activeOnly=false so CANCELLED/BEING_CANCELLED companies are found for status penalty"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_changed: 4
---

# Phase 8 Plan 01: ZefixClient Implementation Summary

**One-liner:** Credential-gated ZefixClient with _Budget + Semaphore + Retry-After backoff, zefix-v1 cache namespace with negative-hit caching, and ZefixFacts dataclass — 10 new tests, 216 total green.

## What Was Built

### Task 1 — RED scaffold (commit cbc69a8)

- `ZefixFacts` dataclass added to `lead_analyzer/models.py` (7 JSON-native fields: `legal_form_de`, `legal_form_fr`, `status`, `uid`, `legal_seat`, `source_url`, `source="zefix"`)
- Three Config fields added to `lead_analyzer/config.py`: `use_zefix: bool = True`, `zefix_concurrency: int = 2`, `zefix_budget: int = 200`
- `tests/test_zefix_client.py` created with all 10 binding test function names, using `requests.post` monkeypatching and injected no-op sleep
- Suite RED: `ModuleNotFoundError` on `lead_analyzer.clients.zefix` (intended)

### Task 2 — GREEN implementation (commit b48fd8e)

- `lead_analyzer/clients/zefix.py` created, mirroring `pagespeed.py` structure exactly:
  - `_Budget` — thread-safe per-run call counter (PERF-02)
  - `ZefixClient.from_config` — returns `None` without `ZEFIX_USER`/`ZEFIX_PASSWORD` (offline-identical run preserved)
  - `ZefixClient.lookup` — cache check → budget gate → POST → parse → cache; never raises
  - `ZefixClient._request` — semaphore-wrapped POST with capped retries + Retry-After backoff
  - `_parse` — exactly-1-result rule; 0 or >1 → None (AC5: no wrong attribution)
  - `_backoff_delay` / `_parse_retry_after` — copied verbatim from pagespeed.py, marked as future-refactor candidates
- Security: credentials stored only as `self._auth` (base64); never logged, cached, or serialized (T-08-01)
- source_url constructed from `ehraid` integer to fixed zefix.admin.ch path; no URL echoed from response (T-08-02)

## Test Results

```
10 passed (tests/test_zefix_client.py)
216 passed total (full suite — was 206 before this plan)
```

## Decisions Made

1. **_Budget + backoff copied verbatim** from `pagespeed.py` rather than extracting to a shared module — scope of this plan is the client only; extraction is a future refactor. Both copies marked with `# future refactor candidate` comment.
2. **`use_zefix=True` as default** — mirrors `use_pagespeed=True`; the `from_config` credential gate already prevents any network call without env vars. The flag exists for `--no-zefix` CLI override in plan 08-02.
3. **`canton` in cache key** — cache key is `["zefix-v1", name, canton or ""]` to avoid false cache hits between same-named companies in different cantons.
4. **`activeOnly=False`** — CANCELLED/BEING_CANCELLED companies must be found so the status penalty (plan 08-02) can be applied correctly; `activeOnly=True` would silently fall back to the name heuristic for dissolved companies.

## Deviations from Plan

None — plan executed exactly as written. All 10 test names match the binding list from 08-VALIDATION.md. All acceptance criteria grep checks pass.

## Threat Model Coverage

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-08-01 Info Disclosure (creds in logs/cache) | Only `self._auth` (base64) stored; `os.environ.get` reads in `from_config` only | MITIGATED |
| T-08-02 Tampering (source_url echoed) | `source_url` constructed from integer `ehraid` to fixed path | MITIGATED |
| T-08-03 Tampering (name injection) | `requests.post(json=body)` auto-encodes; name length-guarded | MITIGATED |
| T-08-04 DoS (malformed response crashes row) | `_parse` wraps in try/except; `lookup`/`_request` never raise | MITIGATED |
| T-08-06 Repudiation (wrong attribution) | `_parse` returns None unless exactly 1 result | MITIGATED |

## Known Stubs

None — this plan delivers only the client layer (network I/O + cache). Score wiring (`payment.estimate()`, `pipeline.run()`) is plan 08-02.

## Threat Flags

None — no new network endpoints beyond the single fixed `zefix.admin.ch` POST. No new auth paths beyond env-var credential reading already present for pagespeed.

## Self-Check: PASSED

- `lead_analyzer/clients/zefix.py`: FOUND
- `tests/test_zefix_client.py`: FOUND
- `ZefixFacts` in `models.py`: FOUND (1 class)
- `use_zefix` in `config.py`: FOUND
- commit `cbc69a8` (RED): FOUND
- commit `b48fd8e` (GREEN): FOUND
- 216 tests passing: VERIFIED
