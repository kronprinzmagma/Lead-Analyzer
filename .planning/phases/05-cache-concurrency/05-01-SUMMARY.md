---
phase: 05-cache-concurrency
plan: 01
subsystem: cache + serialization
tags: [cache, perf-01, ac7, ac4, serialization, cache-aside]
requires: [FetchResult, fetch.fetch, Config.use_cache]
provides: [lead_analyzer.cache, FetchResult.to_dict, FetchResult.from_dict, fetch._fetch_network]
affects: [lead_analyzer/fetch.py, lead_analyzer/models.py, tests/conftest.py]
tech-stack:
  added: [hashlib, tempfile, threading (stdlib only)]
  patterns: [cache-aside, atomic-write-via-os.replace, sha256-keying]
key-files:
  created: [lead_analyzer/cache.py, tests/test_cache.py]
  modified: [lead_analyzer/models.py, lead_analyzer/fetch.py, tests/conftest.py]
decisions:
  - "Gecacht wird das ROHE FetchResult, nicht die Scores (Phase-6-Scoring-Aenderungen erzwingen keinen Re-Crawl)."
  - "Cache-Key = sha256 des \\n-getrennten Kandidaten-Tupels -> deterministisch + traversal-sicher."
  - "Atomares Schreiben via tempfile.mkstemp + os.replace unter threading.Lock."
metrics:
  duration: ~10min
  completed: 2026-06-14
---

# Phase 5 Plan 01: Cache + Serialization Summary

Transparenter Per-URL-JSON-Cache (cache-aside in fetch.fetch) mit atomarem,
thread-sicherem Schreiben (tempfile + os.replace unter Lock) und verlustfreier
FetchResult-Serialisierung; stdlib only.

## What Was Built

- **lead_analyzer/cache.py** (neu): `key_for` (sha256-Hexdigest), `get` (wirft nie -> Miss bei korrupt/fehlend/Schema-Mismatch, AC4), `put` (atomar via tempfile.mkstemp + os.replace unter `_LOCK`), `set_cache_dir`. Schema-versioniert (`schema_version=1`).
- **FetchResult.to_dict/from_dict** (models.py): `asdict` round-trip; `from_dict` toleriert fehlende Keys.
- **Cache-aside in fetch.fetch** (fetch.py): HTTP-Körper verbatim nach `_fetch_network` extrahiert; `fetch()` ist jetzt die Hülle — Hit ohne Netz, Miss schreibt, `use_cache=False` umgeht beides.
- **W3-Fix** (conftest.py): autouse `_isolate_cache`-Fixture lenkt JEDEN Cache-Zugriff in tmp_path (lazy import -> bricht RED-Collection nicht). Repo cache/ bleibt garantiert leer.

## Tasks Completed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 0 | RED: failing cache + serialization tests | 89ae09a |
| 1 | GREEN: atomic cache + FetchResult serialization | f922fc3 |
| 2 | GREEN: cache-aside inside fetch.fetch | 3fd8d6e |

## Tests

10 neue Tests in tests/test_cache.py (7 cache/serialization + 3 cache-aside). Volle Suite: **172 passed** (162 Bestand + 10). Repo cache/ existiert nach pytest-Lauf nicht (0 Pollution).

## Deviations from Plan

- W2 (Extraktion separat committen) wurde pragmatisch mit der cache-aside-Hülle in EINEM Commit (3fd8d6e) zusammengefasst: eine reine Extraktion ohne Hülle hätte `fetch()` temporär entfernt und alle bestehenden fetch-Tests rot gemacht (nicht bisectable-grün). Beide Schritte gemeinsam halten jeden Commit grün. HTTP-Körper wurde dennoch VERBATIM verschoben (timeout, headers, redirect-cap, stream+size cap, SSL-Signal, exception map, session.close).
- Sonst: Plan exakt wie geschrieben umgesetzt.

## Self-Check: PASSED

- lead_analyzer/cache.py — FOUND
- lead_analyzer/models.py (to_dict) — FOUND
- tests/test_cache.py — FOUND
- Commits 89ae09a, f922fc3, 3fd8d6e — FOUND
