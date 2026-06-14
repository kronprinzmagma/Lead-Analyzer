---
phase: 05-cache-concurrency
plan: 02
subsystem: concurrency + CLI flags
tags: [concurrency, perf-03, ac1, ac4, threadpool, cli, resume]
requires: [lead_analyzer.cache, fetch._fetch_network, scoring.stable_sort, analyze_row]
provides: [run() ThreadPoolExecutor, --workers, --no-cache]
affects: [lead_analyzer/pipeline.py, lead_analyzer/cli.py]
tech-stack:
  added: [concurrent.futures (stdlib)]
  patterns: [index-preserving fan-out/fan-in, stable-sort determinism]
key-files:
  created: [tests/test_concurrency.py]
  modified: [lead_analyzer/pipeline.py, lead_analyzer/cli.py]
decisions:
  - "Index-erhaltende fan-in: jeder Future schreibt genau einen festen Index -> keine geteilte mutable Stelle."
  - "Determinismus via stable_sort (Tiebreaker index) -> Output unabhängig von Completion-Reihenfolge."
  - "analyze_row UNVERAENDERT -> Per-Row-Boundary intakt, fut.result() kann nicht re-raisen."
metrics:
  duration: ~8min
  completed: 2026-06-14
---

# Phase 5 Plan 02: Concurrency + CLI Flags Summary

run() fächert über Zeilen mit ThreadPoolExecutor(max_workers=config.workers) auf
(index-erhaltender fan-in); Output bleibt byte-identisch zum sequentiellen Lauf
(stable_sort). --workers / --no-cache von der CLI in die Config verdrahtet.

## What Was Built

- **pipeline.run() parallelisiert**: `ThreadPoolExecutor(max_workers=config.workers)`, `submit(analyze_row, ...)` pro Record, fan-in nach festem Original-Index via `futs[fut]`, `assert all(... is not None)`. `stable_sort` + len-Invariante + write_output UNVERAENDERT.
- **CLI-Flags** (cli.py): `--workers N` (default 8), `--no-cache` (store_true) -> `Config(workers=, use_cache=not no_cache)`.

## Tasks Completed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 0 | RED: concurrency determinism/isolation/flag/resume tests | f415915 |
| 1 | GREEN: parallelize run() with ThreadPoolExecutor | ac77ee3 |
| 2 | GREEN: wire --workers and --no-cache CLI flags | f7deb18 |

## Tests

5 neue Tests in tests/test_concurrency.py (determinism, isolation, --workers, --no-cache, resume). Volle Suite: **177 passed** (162 Bestand + 10 cache + 5 concurrency).

## Live Phase-Gate Evidence

`python run.py data/sample_input.xlsx -o output/phase5_check.xlsx --workers 8`, 42 Zeilen, zweimal:

| Lauf | Cache | Wall-clock |
| ---- | ----- | ---------- |
| 1 (cold) | leer -> 41 Files geschrieben | 6.20 s |
| 2 (warm) | alle Hits | 0.93 s (~6.7x schneller) |

- Outputs beider Läufe **byte-identisch** (headers + alle Zellen, 42 Zeilen).
- Repo cache/ genutzt (41 Cache-Files nach Lauf 1).
- Nach pytest-Lauf: repo cache/ unverändert (41 -> 41) — kein Test-Pollution (W3).

## Deviations from Plan

None — Plan exakt wie geschrieben umgesetzt.

## Self-Check: PASSED

- tests/test_concurrency.py — FOUND
- ThreadPoolExecutor in pipeline.py — FOUND (grep count 2)
- --workers/--no-cache in cli.py — FOUND (grep count 2)
- Commits f415915, ac77ee3, f7deb18 — FOUND
