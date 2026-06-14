---
phase: 5
slug: cache-concurrency
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 5 — Validation Strategy

> Derived from 05-RESEARCH.md. Fully offline: cache tests use tmp dirs; concurrency tests monkeypatch fetch. Output must be byte-for-byte identical to Phase 4 (cache + threads are transparent).

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Quick run** | `python -m pytest tests/ -q` |
| **Network policy** | autouse conftest fixture fails any un-mocked request |
| **Cache isolation** | tests set cache dir to tmp_path, never repo cache/ |

## Per-Requirement Verification Map

| Requirement | Observable validation | Test type | Status |
|---|---|---|---|
| **PERF-01** (resumable per-URL cache, atomic, abort-safe — AC7) | FetchResult round-trips to/from JSON; key = sha256(normalized candidates); cache-aside in fetch.fetch (hit → no network); atomic temp+os.replace; corrupt/missing file → miss (no crash); re-run skips already-cached URLs (zero re-fetch). | unit (tmp dir) + resume test | Pending |
| **PERF-03** (concurrency for hundreds of rows; flags — AC1) | ThreadPoolExecutor(max_workers=config.workers) in run(); output identical to sequential (same rows, sort, columns); --workers N + --no-cache wired; per-row exception isolation preserved under threads. | unit (monkeypatched fetch) + determinism test | Pending |

## Offline Integration Check

`python run.py data/sample_input.xlsx -o out.xlsx --workers 8` then re-run: second run hits cache (no re-fetch), output identical. `--no-cache` bypasses. Threaded output == `--workers 1` output (same scores/sort/columns).

## Wave 0 — Test File Gaps

- tests/test_cache.py (new) — to_dict/from_dict round-trip, key determinism, hit/miss, atomic write, corrupt-file tolerance, set_cache_dir(tmp_path).
- tests/test_concurrency.py (new) — threaded run preserves order/sort/columns vs sequential; per-row isolation under threads; --workers/--no-cache effect.
- extend tests/test_fetch.py — cache-aside hit skips network (monkeypatched).
