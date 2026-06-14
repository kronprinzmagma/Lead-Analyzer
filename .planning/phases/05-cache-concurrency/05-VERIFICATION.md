---
phase: 05-cache-concurrency
verified: 2026-06-14T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
gaps: []
---

# Phase 5: Cache + Concurrency Verification Report

**Phase Goal:** Runs are resumable and fast enough for hundreds of rows via a per-URL cache and threaded fetch.
**Verified:** 2026-06-14
**Status:** passed
**Re-verification:** No — initial verification

Verification method: goal-backward. SUMMARY claims were NOT trusted; every load-bearing
behavior (resume, determinism, atomicity, no-cache bypass, test isolation) was re-proven
with independent offline scripts plus targeted test runs.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Per-URL results cached incrementally with atomic temp-file+replace; re-run skips analyzed URLs; interrupted run keeps completed work (AC7/PERF-01) | VERIFIED | `cache.put` uses `tempfile.mkstemp(dir=...)` + `os.replace` under `_LOCK` (cache.py:77-90); per-URL file `{key}.json`. Independent offline run: cold run = 41 network calls, warm run = +0 (RESUME OK True). Concurrent 12-thread stress: 0 torn reads, 0 `.tmp` leftovers. |
| 2 | Orchestrator fetches concurrently (thread pool); hundreds of rows fast; stages skippable via flag (AC1/PERF-03) | VERIFIED | `ThreadPoolExecutor(max_workers=config.workers)` in `pipeline.run()` (pipeline.py:95-100); index-preserving fan-in via `futs[fut]`. `--workers` (default 8) and `--no-cache` wired (cli.py:34-41, 54-55). `--no-cache` independently confirmed: re-fetches all rows, writes 0 cache files. SUMMARY's live run: 6.20s cold -> 0.93s warm (~6.7x). |
| 3 | Caching+concurrency preserve correctness: all rows, correct sort, unchanged original columns | VERIFIED | Independent offline run: workers=1 output == workers=8 output, cell-for-cell (`rows1 == rows8` True), headers identical, 42 rows preserved. Output sorted desc by Bedarf then Zahl (True). `pipeline.py` diff (798f35c..HEAD) touches ONLY `run()` orchestration — no bedarf/zahl/scoring/sort logic changed; `analyze_row` body untouched (transparency proven structurally + empirically). |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lead_analyzer/cache.py` | atomic per-URL cache, sha256 key, never-raising get | VERIFIED | 91 lines, substantive. `key_for` sha256 hexdigest (traversal-safe); `get` catches FileNotFound/JSONDecode/OSError/ValueError -> None; schema_version gate; `put` atomic under Lock. |
| `lead_analyzer/models.py` (FetchResult to_dict/from_dict) | lossless serialization, tolerant from_dict | VERIFIED | `to_dict` via `asdict`; `from_dict` uses `.get(...)` defaults -> no KeyError on schema bump. Round-trip test green. |
| `lead_analyzer/fetch.py` (cache-aside) | fetch() = cache shell over _fetch_network | VERIFIED | `fetch()` reads cache on hit (no network/session), writes on miss, bypasses both when `use_cache=False` (fetch.py:113-131). RAW FetchResult cached, not scores. |
| `lead_analyzer/pipeline.py` (run threaded) | ThreadPoolExecutor, index-preserving | VERIFIED | pipeline.py:93-107. Stable sort + len invariant unchanged. |
| `lead_analyzer/cli.py` (flags) | --workers / --no-cache | VERIFIED | cli.py:34-41 args, 54-55 -> Config. |
| `tests/test_cache.py` | cache + cache-aside tests | VERIFIED | 10 tests, real assertions (round-trip equality, corrupt/missing/stale=miss, no .tmp left, hit-skips-net, miss-then-put count, no-cache bypass). |
| `tests/test_concurrency.py` | determinism/isolation/flags/resume | VERIFIED | 5 tests; resume spies `_fetch_network` and asserts no extra calls (honest); determinism compares real cell dicts (honest). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| fetch.fetch | cache.get/put | key_for(candidates) cache-aside | WIRED | hit returns from_dict without network; miss calls _fetch_network then put |
| pipeline.run | analyze_row | ThreadPoolExecutor.submit, fan-in by index | WIRED | results[i]=fut.result(); assert no None |
| cli.main | Config(workers,use_cache) | argparse --workers/--no-cache | WIRED | not no_cache -> use_cache |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `pytest tests/ -q` | 177 passed in 0.34s | PASS |
| Resume (no refetch) | offline run, spy _fetch_network | cold 41, warm +0 | PASS |
| Determinism | workers=1 vs workers=8 cells | identical, 42 rows | PASS |
| no-cache bypass | use_cache=False x2 | re-fetched all, 0 json written | PASS |
| Atomicity under contention | 12 threads x 50 put/get | 0 torn reads, 0 .tmp left | PASS |
| Test pollution | pytest, compare repo cache/ | 41 -> 41, no .tmp | PASS |
| Sort order | output cells | desc by Bedarf,Zahl | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PERF-01 | 05-01 | Resumable atomic per-URL cache (AC7) | SATISFIED | cache.py atomic write + resume proven |
| PERF-03 | 05-02 | Concurrency (AC1) | SATISFIED | ThreadPoolExecutor in run() + flags |

### Anti-Patterns Found

None. No TODO/FIXME/placeholder/stub in the Phase 5 files. `cache.get` returning None is intentional miss semantics (not a stub). `put` cleanup-on-error re-raises (correct).

### Honesty Audit (Check 5)

- Resume test (`test_resumability_skips_cached`): spies `_fetch_network`, asserts `len(calls) == after_first` after a full second `run()`. Genuinely proves no refetch — NOT a count-of-mock-output trick. HONEST.
- Determinism test (`test_threaded_equals_sequential`): asserts `rows1 == rows8` on real cell dicts read back from xlsx, not counts. HONEST.
- Network block (conftest `_block_network`) is autouse and active, so cache-hit tests passing genuinely prove zero network contact. HONEST.
- Cache isolation (conftest `_isolate_cache` autouse -> tmp_path) verified: repo `cache/` unchanged (41->41) across pytest runs. No pollution.

### Gaps Summary

None. All three success criteria, both requirements (PERF-01, PERF-03), and the
load-bearing transparency property (byte-for-byte identical output across
workers and cache hit/miss) are independently verified in the codebase.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
