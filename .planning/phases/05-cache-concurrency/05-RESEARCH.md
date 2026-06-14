# Phase 5: Cache + Concurrency - Research

**Researched:** 2026-06-14
**Domain:** Resumable per-URL disk cache + threaded fan-out for a stdlib Python CLI batch enricher
**Confidence:** HIGH (stdlib-only patterns: `concurrent.futures`, `json`, `hashlib`, `os.replace`, `threading.Lock`; all verified against the existing codebase)

## Summary

Phase 5 makes the existing sequential pipeline **fast** and **resumable** without changing a single score. Two transparent layers are added under the existing `fetch.fetch()` seam and around the existing `analyze_row()` loop:

1. **Cache-aside (PERF-01 / AC7):** one small JSON file per URL under `cache/`, keyed by a SHA-256 hash of the *normalized candidate tuple*, written atomically (temp file + `os.replace`) immediately after each fetch. A re-run reads the cache and skips the HTTP call entirely; a kill mid-run leaves every already-fetched URL on disk, so re-running resumes. The cache stores the **raw `FetchResult`** (the cacheable unit, per `models.py` docstring), NOT the final scores — so scoring tweaks in later phases never force a re-crawl.

2. **Thread pool (PERF-03 / AC1):** the orchestrator's list comprehension over `analyze_row` is replaced by `ThreadPoolExecutor(max_workers=config.workers)`. Work is I/O-bound (one HTTP GET per row), so threads are correct and stdlib-only; the GIL is irrelevant because workers block on the network. Results are collected into a list indexed by submission order so the existing stable sort stays loss-free and **byte-identical to the sequential output**.

**Primary recommendation:** Add a new `lead_analyzer/cache.py` (key/get/put, atomic, thread-safe). Wrap caching *inside* `fetch.fetch()` so `analyze_row` is unchanged and all offline tests keep passing. Parallelize at the `run()` level only. Wire `--workers N` and `--no-cache` from the already-existing `Config.workers` / `Config.use_cache` fields. Keep the cache directory configurable so tests use `tmp_path`, never the repo `cache/`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-URL disk cache (read/write/atomic) | `cache.py` (new I/O module) | `fetch.py` (call site) | Cache is a storage concern; sits *under* fetch per ARCHITECTURE.md so a hit skips HTTP |
| Cache-aside decision (hit vs. miss) | `fetch.fetch()` | `config` (use_cache flag) | Fetch owns "do I need the network?"; keeps `analyze_row` ignorant of caching |
| Serialization (`FetchResult` ↔ dict) | `models.py` (`to_dict`/`from_dict`) | `cache.py` (JSON) | Dataclass owns its own JSON shape; cache stays generic |
| Concurrency / fan-out over rows | `pipeline.run()` | `concurrent.futures` | Orchestrator owns lifecycle; analyzers stay pure-ish |
| Per-row exception isolation | `analyze_row()` (already) | `pipeline.run()` (future.result) | Already never raises; pool must not reintroduce a crash path |
| Thread-safe cache writes | `cache.py` (module-level `Lock`) | — | One lock, one-file-per-URL → no cross-row contention |
| Flag wiring (`--workers`, `--no-cache`) | `cli.py` | `config.py` (fields exist) | CLI builds Config; fields already declared |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `concurrent.futures` (stdlib) | Python 3.14 | `ThreadPoolExecutor` fan-out/fan-in | Canonical I/O-bound batch pattern; no new dep [VERIFIED: project runs Python 3.14.3] |
| `json` (stdlib) | Python 3.14 | Serialize `FetchResult` to per-URL cache file | Human-readable, debuggable cache (transparency over elegance, CLAUDE.md §5) [VERIFIED: codebase] |
| `hashlib` (stdlib) | Python 3.14 | SHA-256 of normalized URL tuple → cache filename | Collision-resistant, filesystem-safe fixed-length names [VERIFIED: codebase] |
| `os` (stdlib) | Python 3.14 | `os.replace` atomic rename; `os.makedirs` | `os.replace` is atomic on POSIX and Windows for same-filesystem renames [CITED: docs.python.org/3/library/os.html#os.replace] |
| `threading` (stdlib) | Python 3.14 | `threading.Lock` guarding cache writes | Standard guard for shared mutable disk state |
| `tempfile` (stdlib) | Python 3.14 | temp file in cache dir before atomic replace | Ensures the temp lives on the same filesystem as the target (so `os.replace` stays atomic) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib.Path` (stdlib) | Python 3.14 | Cache dir / file path construction | Cleaner than string joins; use for the cache root |
| `dataclasses.asdict` (stdlib) | Python 3.14 | Optional helper inside `FetchResult.to_dict` | `FetchResult` is a flat dataclass with JSON-native fields → `asdict` works directly |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One JSON file per URL | Single big JSON / SQLite / `shelve` | Single file: a mid-write crash corrupts the *whole* cache (ARCHITECTURE.md Anti-Pattern 3, PITFALLS.md #11). SQLite: extra concurrency/locking complexity, harder to inspect, new mental model. One-file-per-URL is the most crash-safe and contention-free. **Reject alternatives.** |
| `ThreadPoolExecutor` | `multiprocessing` / `asyncio` | Processes: pointless for I/O-bound work + pickling overhead. asyncio: would require rewriting `requests` to an async client (new dep, violates constraints). Threads are correct here. **Reject alternatives.** |
| SHA-256 of candidate tuple | `urllib.parse.quote` of URL as filename | quote() can still produce over-long names and collide on `/` vs `%2F`; hashing gives fixed-length, collision-resistant, FS-safe names. **Use SHA-256.** |
| `as_completed` | `executor.map` | `map` returns in submission order (convenient) but `as_completed` lets us write progress as rows finish. Both work; see Concurrency decision below. |

**Installation:** None. Phase 5 adds **zero** dependencies — all stdlib (constraint honored).

**Version verification:** No registry packages to verify; `requests`, `openpyxl`, `bs4` are already installed from Phases 1–4 and unchanged here.

## Architecture Patterns

### System Architecture Diagram

```
                         pipeline.run(config)
                                │
              read_rows ──► records[]  (RowRecord, .index intact)
                                │
                                ▼
        ┌───────────────────────────────────────────────────┐
        │  ThreadPoolExecutor(max_workers=config.workers)     │
        │     submit analyze_row(record, url_col, config)     │
        │     for each record  ──►  futures keyed by index    │
        └───────────────────────────────────────────────────┘
                                │  (per row, in a worker thread)
                                ▼
            analyze_row  ──►  fetch.normalize(cell)
                                │ candidates[]
                                ▼
                          fetch.fetch(candidates, config)
                                │
                ┌───────────────┴───────────────┐
        use_cache?                          (miss)
                │ key = cache.key_for(candidates)   │
                ▼                                    ▼
        cache.get(key) ──hit──► FetchResult   HTTP GET (Phase 2 logic)
                │ (no network)                       │ FetchResult
                │                                     ▼
                │                          cache.put(key, fr.to_dict())
                │                          [temp file + os.replace, Lock]
                └───────────────┬─────────────────────┘
                                ▼  FetchResult (raw signals)
                  parse-once soup ──► 6 dim analyzers + payment
                                ▼  RowResult(index, bedarf, zahl, reason)
                                │
        fan-in: results[index] = future.result()   (never raises, AC4)
                                ▼
              scoring.stable_sort(zip(records, results))
                                ▼
              table_io.write_output(...)  ← identical bytes to Phase 4
```

The cache sits **under** `fetch.fetch()`: a hit returns a `FetchResult` without touching the network or the soup/analyzer chain re-runs, so scoring stays deterministic and re-runs are fast. The diagram's single network arrow is the only place HTTP happens — unchanged from Phase 2.

### Recommended Project Structure
```
lead_analyzer/
├── cache.py          # NEW: key_for(), get(), put(), set_cache_dir() — atomic + thread-safe
├── fetch.py          # MODIFIED: fetch() consults cache before HTTP, writes on miss
├── models.py         # MODIFIED: FetchResult.to_dict() / from_dict()
├── pipeline.py       # MODIFIED: run() uses ThreadPoolExecutor; analyze_row UNCHANGED
├── cli.py            # MODIFIED: --workers, --no-cache → Config
└── config.py         # UNCHANGED: workers / use_cache fields already exist
tests/
├── test_cache.py     # NEW: round-trip, atomic, hit/miss, corrupt-file tolerance
├── test_concurrency.py  # NEW: ordering preserved, threaded==sequential, resumability
└── conftest.py       # UNCHANGED autouse network block; reuse make_fetch_result
cache/                # gitignored (already in .gitignore) — runtime only, NEVER touched by tests
```

### Pattern 1: Cache-aside inside `fetch.fetch()` (PERF-01, AC7)

**What:** Before the HTTP probe, compute a key from the candidate list; if `use_cache` and a valid cache entry exists, deserialize and return it. On a miss (or `--no-cache`), run the existing HTTP logic, then write the result atomically before returning.

**When to use:** Every fetch in normal operation; bypass entirely when `config.use_cache is False`.

**Why inside fetch (not a wrapper):** ARCHITECTURE.md says "the cache sits under fetch so a cache hit skips both HTTP and PageSpeed." Putting it inside `fetch.fetch()` keeps `analyze_row` byte-for-byte unchanged → all 162 existing tests stay green, and offline tests that monkeypatch the network still work (a cache hit just never reaches the network block).

**Example (integration sketch — verify against current fetch.py):**
```python
# fetch.py — top of fetch(), before building the Session
def fetch(candidates: list[str], config) -> FetchResult:
    use_cache = getattr(config, "use_cache", True)
    key = None
    if use_cache and candidates:
        key = cache.key_for(candidates)          # hash of the normalized tuple
        cached = cache.get(key)                   # None on miss / corrupt / missing
        if cached is not None:
            return FetchResult.from_dict(cached)  # NO network, NO Session created

    fr = _fetch_network(candidates, config)       # existing Phase-2 body, refactored out
    if use_cache and key is not None:
        cache.put(key, fr.to_dict())              # atomic, thread-safe, incremental
    return fr
```
> Note: extract the current `try/finally` HTTP body into a private `_fetch_network(candidates, config)` so the cache check brackets it cleanly. The HTTP logic itself does not change.

### Pattern 2: Cache key = SHA-256 of the normalized candidate tuple (PITFALLS.md #12)

**What:** Key on the **normalized candidates** (the output of `fetch.normalize`), not the raw cell and not the final fetched URL.

**Why the candidate tuple (the resolved decision):**
- **Not the raw cell:** ` example.ch `, `example.ch`, `EXAMPLE.ch` should hit the same entry; the raw cell carries whitespace/case noise. Normalization already collapses these (`fetch.normalize` lowercases host, strips, builds variants).
- **Not the final fetched URL:** the final URL is only known *after* the fetch — useless as a pre-fetch lookup key, and a redirect target could collide across inputs.
- **The candidate tuple is the deterministic function of the input** that drives the fetch: same input cell → same candidate list → same key → cache hit on re-run. This is exactly what AC7 resumability needs.

```python
# cache.py
import hashlib, json
def key_for(candidates: list[str]) -> str:
    # Join with a separator that cannot appear in a URL host/path ambiguously;
    # hash gives a fixed-length, filesystem-safe filename stem.
    canon = "\n".join(candidates)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
```
Stamp each cache entry with a `schema_version` (or `logic_version`) integer so a future change to what `FetchResult` stores can invalidate old entries by ignoring mismatched versions on read (PITFALLS.md #12). Phase 5 starts at version 1.

### Pattern 3: Atomic, thread-safe incremental write (PITFALLS.md #11, AC7)

**What:** Write JSON to a temp file in the cache dir, `os.replace` it onto the final name, under a module-level `threading.Lock`. One file per URL means writes never contend across rows; the lock only guards against the (rare) same-key concurrent write and keeps the dir-creation race-free.

```python
# cache.py
import json, os, tempfile, threading
from pathlib import Path

_LOCK = threading.Lock()
_CACHE_DIR = Path("cache")

def set_cache_dir(path) -> None:        # tests call this with tmp_path
    global _CACHE_DIR
    _CACHE_DIR = Path(path)

def _path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"

def get(key: str):
    p = _path(key)
    try:
        with p.open("r", encoding="utf-8") as f:
            entry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None                      # miss OR corrupt → re-fetch, NEVER crash (AC4)
    if entry.get("schema_version") != 1:
        return None                      # stale schema → treat as miss
    return entry.get("payload")

def put(key: str, payload: dict) -> None:
    entry = {"schema_version": 1, "payload": payload}
    with _LOCK:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=_CACHE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            os.replace(tmp, _path(key))  # atomic same-filesystem rename
        except BaseException:
            try: os.unlink(tmp)
            except OSError: pass
            raise
```
Reads are intentionally lock-free: `os.replace` is atomic, so a reader either sees the old complete file or the new complete file, never a half-written one.

### Pattern 4: Fan-out over rows, index-preserving fan-in (PERF-03, AC1, AC2)

**What:** Submit `analyze_row` for every record; collect each future's result into a results list positioned by submission index, then hand `zip(records, results)` to the existing `scoring.stable_sort`. Output order and content are identical to sequential because the sort key (`-bedarf, -zahl, index`) is fully determined by the inputs, not by completion order.

```python
# pipeline.py — run()
from concurrent.futures import ThreadPoolExecutor, as_completed

results: list[RowResult | None] = [None] * len(records)
workers = max(1, getattr(config, "workers", 8))
with ThreadPoolExecutor(max_workers=workers) as pool:
    futs = {pool.submit(analyze_row, r, url_col, config): i
            for i, r in enumerate(records)}
    for fut in as_completed(futs):
        i = futs[fut]
        results[i] = fut.result()        # analyze_row never raises (AC4 boundary intact)

assert all(r is not None for r in results), "Pool dropped a row!"
pairs = list(zip(records, results))
ordered = scoring.stable_sort(pairs)
```
`analyze_row` is **unchanged** — its existing per-row `try/except` (ROB-03) means `future.result()` never re-raises. A `workers=1` path is equivalent to sequential and is the natural determinism baseline for tests.

### Anti-Patterns to Avoid
- **Single big cache file written at exit** — a mid-write crash corrupts everything and an abort loses all work (ARCHITECTURE.md AP3, PITFALLS.md #11). Use one atomic file per URL.
- **Caching the final scores instead of the raw `FetchResult`** — a scoring tweak (Phase 6 PageSpeed, payment changes) would force a full re-crawl. Cache the raw signals (`FetchResult`); re-scoring reads cached signals (PITFALLS.md #12, technical-debt table).
- **Keying on the raw cell or final URL** — splits/merges cache entries wrongly (PITFALLS.md #12). Key on the normalized candidate tuple.
- **Parallelizing inside `analyze_row` or the analyzers** — keep concurrency at the `run()` boundary only; per-row code stays single-threaded and pure-ish.
- **Sorting original rows in place** — keep `index` on every record, sort a list of result pairs (ARCHITECTURE.md AP1, PITFALLS.md #10). Already correct; do not regress.
- **Letting the pool reintroduce a crash path** — never wrap `analyze_row` in a way that swallows then re-raises; call `future.result()` directly (it can't raise because `analyze_row` doesn't).
- **Tests writing to the repo `cache/`** — always `cache.set_cache_dir(tmp_path)` in a fixture; otherwise tests pollute/poison each other and the real cache.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Manual write-then-rename with flush juggling | `tempfile.mkstemp(dir=...)` + `os.replace` | `os.replace` is the documented atomic primitive; same-dir temp guarantees same filesystem [CITED: docs.python.org os.replace] |
| Thread pool | Hand-rolled `threading.Thread` + queue | `concurrent.futures.ThreadPoolExecutor` | Battle-tested, handles worker lifecycle, `as_completed`, exception propagation |
| Cache key | Sanitizing URL into a filename | `hashlib.sha256(...).hexdigest()` | Fixed-length, collision-resistant, filesystem-safe; no `/`, length, or case issues |
| Dataclass → JSON | Manual field listing | `dataclasses.asdict` (flat fields) | `FetchResult` fields are all JSON-native; `asdict` is exact and maintenance-free |
| Concurrent dedup of identical URLs in one run | A shared in-flight-future registry | (Skip in Phase 5) | The disk cache already dedups across runs; same-run duplicate URLs are rare in a customer list. Note as optional future optimization, do not build now. |

**Key insight:** Every primitive Phase 5 needs already exists in the stdlib and is more correct than a hand-rolled version. The phase is *integration*, not invention — the risk is in placement (cache under fetch, concurrency at run) and in test hygiene (tmp dirs, network block), not in the algorithms.

## Runtime State Inventory

This phase **introduces** runtime state (the cache) rather than renaming it, so the rename inventory is mostly N/A — but the new state must be enumerated so later phases and tests know it exists:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | NEW: `cache/<sha256>.json` per URL, written at runtime. Each holds `{schema_version, payload(FetchResult)}`. | None to migrate (greenfield cache). Document `--no-cache` and "delete `cache/` for a fresh run" in README (Phase 7). |
| Live service config | None — verified: no external service config touched by this phase. | None |
| OS-registered state | None — verified: no scheduler/daemon (CLI only, §6). | None |
| Secrets/env vars | None — cache holds public website HTML/headers only; no keys involved (PageSpeed is Phase 6). | None |
| Build artifacts | None — no packaging/rename; `cache/` already in `.gitignore` (verified). | None |

**Cache privacy note (§6, PITFALLS.md #18):** cached files contain scraped website HTML/headers — exactly the data §6 says to keep local. `cache/` is already gitignored (verified in `.gitignore`). Do not log full cached HTML.

## Common Pitfalls

### Pitfall 1: Cache corruption / partial write breaks the NEXT run (PITFALLS.md #11)
**What goes wrong:** A non-atomic `open('w')` + `json.dump` killed mid-write leaves a truncated file; the next run's `json.load` throws and re-introduces a crash path.
**Why it happens:** Writing directly to the final filename.
**How to avoid:** temp file + `os.replace`; `get()` catches `JSONDecodeError`/`OSError` and treats it as a miss (re-fetch), never propagating.
**Warning signs:** zero-byte `.json` files; `JSONDecodeError` on a second run.

### Pitfall 2: Stale cache hides a fixed analyzer (PITFALLS.md #12)
**What goes wrong:** After changing what `FetchResult` stores, old entries lack new fields → `from_dict` KeyErrors or silently wrong signals.
**Why it happens:** No version on cache entries.
**How to avoid:** `schema_version` stamp; `get()` returns `None` on mismatch. `from_dict` must tolerate missing optional keys defensively.
**Warning signs:** scores unchanged after a fix; `KeyError` in `from_dict`.

### Pitfall 3: Concurrency silently changes the output (AC2/AC3 regression)
**What goes wrong:** Collecting results in completion order instead of by index scrambles ties; or a dropped future leaves a `None` in results.
**Why it happens:** Using `as_completed` results without re-indexing.
**How to avoid:** key futures by submission index; assert no `None` remains; rely on `stable_sort`'s `index` tiebreaker. **Test: threaded run == sequential run, byte-for-byte.**
**Warning signs:** output row order differs between `--workers 1` and `--workers 8`.

### Pitfall 4: Tests hit the real network or pollute the real cache
**What goes wrong:** A cache *miss* in a test would reach the HTTP path; the autouse network block then fires an `AssertionError`. Or a test writes into the repo `cache/`.
**Why it happens:** Forgetting to monkeypatch `fetch` / not redirecting the cache dir.
**How to avoid:** Concurrency tests monkeypatch `fetch.fetch` (or `_fetch_network`) with a deterministic fake; cache tests call `cache.set_cache_dir(tmp_path)` via a fixture and never touch the network at all.
**Warning signs:** `AssertionError: network used in tests`; files appearing in `./cache/`.

### Pitfall 5: `os.replace` across filesystems is not atomic
**What goes wrong:** Putting the temp file in `/tmp` and replacing into `cache/` on a different mount loses atomicity (raises `OSError` or falls back to copy).
**Why it happens:** Using `tempfile.NamedTemporaryFile()` with default dir.
**How to avoid:** `tempfile.mkstemp(dir=_CACHE_DIR)` — temp lives beside the target. [CITED: docs.python.org os.replace — "If both are on the same filesystem... atomic"]
**Warning signs:** `OSError: Invalid cross-device link`.

## Code Examples

### FetchResult ↔ dict (models.py)
```python
# models.py — add to FetchResult
from dataclasses import asdict

def to_dict(self) -> dict:
    return asdict(self)          # all fields are JSON-native (str/bool/int/None/dict)

@classmethod
def from_dict(cls, d: dict) -> "FetchResult":
    # Defensive: tolerate missing keys so a schema bump never KeyErrors.
    return cls(
        url=d.get("url", ""),
        ok=d.get("ok", False),
        status=d.get("status"),
        final_url=d.get("final_url"),
        redirected=d.get("redirected", False),
        ssl_ok=d.get("ssl_ok", False),
        headers=d.get("headers", {}),
        html=d.get("html"),
        error=d.get("error"),
    )
```
> All `FetchResult` fields are JSON-serializable as-is: `url:str`, `ok:bool`, `status:int|None`, `final_url:str|None`, `redirected:bool`, `ssl_ok:bool`, `headers:dict`, `html:str|None`, `error:str|None`. No custom encoder needed. [VERIFIED: models.py lines 54-71]

### Round-trip test (offline)
```python
# tests/test_cache.py
from lead_analyzer import cache
from lead_analyzer.models import FetchResult
from conftest import make_fetch_result

def test_round_trip(tmp_path):
    cache.set_cache_dir(tmp_path)
    fr = make_fetch_result(status=403, ok=False, html=None, error="blockiert")
    key = cache.key_for(["https://x.ch", "http://x.ch"])
    cache.put(key, fr.to_dict())
    got = FetchResult.from_dict(cache.get(key))
    assert got == fr                       # dataclass __eq__ → exact equality

def test_corrupt_file_is_a_miss(tmp_path):
    cache.set_cache_dir(tmp_path)
    key = cache.key_for(["https://x.ch"])
    (tmp_path / f"{key}.json").write_text("{ this is not json")
    assert cache.get(key) is None          # tolerated, no crash (AC4)
```

### Concurrency determinism + resumability test (offline)
```python
# tests/test_concurrency.py — fetch is monkeypatched; NO network, NO real cache
def test_threaded_equals_sequential(monkeypatch, tmp_path):
    cache.set_cache_dir(tmp_path)
    monkeypatch.setattr(fetch, "fetch",
        lambda cands, cfg: make_fetch_result(url=cands[0]))
    seq = pipeline.run(Config(input=SAMPLE, output=str(tmp_path/"a.xlsx"), workers=1))
    par = pipeline.run(Config(input=SAMPLE, output=str(tmp_path/"b.xlsx"), workers=8))
    # compare the two written sheets row-by-row → identical

def test_resumability_skips_cached(monkeypatch, tmp_path):
    cache.set_cache_dir(tmp_path)
    calls = []
    real = fetch._fetch_network
    monkeypatch.setattr(fetch, "_fetch_network",
        lambda c, cfg: (calls.append(c[0]), make_fetch_result(url=c[0]))[1])
    # run 1 populates cache; run 2 must NOT call _fetch_network again
    pipeline.run(Config(input=SAMPLE, output=str(tmp_path/"o.xlsx")))
    n_first = len(calls)
    pipeline.run(Config(input=SAMPLE, output=str(tmp_path/"o.xlsx")))
    assert len(calls) == n_first           # second run was all cache hits (AC7)
```
> "Simulated abort" = simply not running every row, or deleting one cache file, then asserting the next run re-fetches only the missing URL. A real `kill -9` is unnecessary because atomic per-URL writes make "completed before abort" exactly "file exists on disk."

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential list comprehension over `analyze_row` (Phase 1–4) | `ThreadPoolExecutor` fan-out, index-preserving fan-in | Phase 5 | Hundreds of rows in minutes not tens of minutes; same output |
| No persistence; every run re-fetches | Per-URL atomic JSON cache, cache-aside under `fetch` | Phase 5 | Re-runs and aborts cost ~nothing; AC7 satisfied |

**Deprecated/outdated:** Nothing removed. The sequential path is preserved as the `workers=1` behavior and the determinism baseline.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Default `workers=8` (existing Config default) is a reasonable politeness/speed balance for third-party Swiss SME sites | Flags / Concurrency | Too high → rude / rate-limited per host; but one URL per host is typical so risk is low. Confirm with PO if politeness matters. |
| A2 | Caching all rows (including same-run duplicate URLs) without an in-flight registry is acceptable — duplicates rare in customer lists | Don't Hand-Roll | If the list has many repeated URLs, a few redundant concurrent fetches occur on first run (still correct, just slightly wasteful). |
| A3 | `models.py`, `pipeline.py`, `fetch.py`, `cli.py`, `cache.py` are the only files touched; `config.py` unchanged | Project Structure | If Phase 6 expects a different cache API, minor refactor later. Low risk — cache API is small. |
| A4 | Sample input path for tests is `data/sample_input.xlsx` (per CLAUDE.md) | Validation | If renamed, test paths need updating. |

**Note:** A1 (default workers) is a `[ASSUMED]` politeness target — the planner/discuss-phase should confirm whether 8 is acceptable or should be lowered (e.g. 4–6) for third-party-site politeness.

## Open Questions

1. **Should identical URLs within a single run be deduplicated before fetch?**
   - What we know: the disk cache dedups across runs; within one run, two rows with the same URL could both fetch before either writes the cache.
   - What's unclear: whether the sample/real lists contain enough duplicate URLs to matter.
   - Recommendation: skip in Phase 5 (correctness is fine, only minor first-run waste). Note as a possible future optimization (in-flight future registry keyed by cache key).

2. **Default `--workers` value for politeness.**
   - What we know: Config default is 8; ARCHITECTURE.md suggests 8–16, PITFALLS.md says keep modest.
   - What's unclear: PO's tolerance for being "rude" to third-party sites.
   - Recommendation: keep 8 as default, expose `--workers`, document the politeness tradeoff in README (Phase 7). Confirm in discuss-phase.

## Environment Availability

> All dependencies are the Python stdlib (`concurrent.futures`, `json`, `hashlib`, `os`, `threading`, `tempfile`, `pathlib`) plus already-installed `requests`/`openpyxl`/`bs4`. No new external tools.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib threading/futures/json/hashlib/os | Cache + concurrency | ✓ | Python 3.14.3 | — |
| `requests`, `openpyxl`, `bs4` | Existing fetch/io (unchanged) | ✓ (Phases 1–4) | installed | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing; 162 tests across 13 files) [VERIFIED: tests/ dir] |
| Config file | none detected — pytest run from repo root; `tests/conftest.py` provides autouse network block + fakes |
| Quick run command | `python3 -m pytest tests/test_cache.py tests/test_concurrency.py -x -q` |
| Full suite command | `python3 -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERF-01 | `FetchResult` round-trips through cache (to_dict/from_dict exact) | unit | `pytest tests/test_cache.py::test_round_trip -x` | ❌ Wave 0 |
| PERF-01 | Atomic write: corrupt/partial cache file → miss, no crash | unit | `pytest tests/test_cache.py::test_corrupt_file_is_a_miss -x` | ❌ Wave 0 |
| PERF-01 | Cache key stable for same normalized candidates; differs for different | unit | `pytest tests/test_cache.py::test_key_stability -x` | ❌ Wave 0 |
| PERF-01 | Re-run skips fetch for cached URLs (resumability/AC7) | integration | `pytest tests/test_concurrency.py::test_resumability_skips_cached -x` | ❌ Wave 0 |
| PERF-01 | `--no-cache` bypasses cache (no read, no write) | unit | `pytest tests/test_concurrency.py::test_no_cache_flag -x` | ❌ Wave 0 |
| PERF-01 | Schema-version mismatch → treated as miss | unit | `pytest tests/test_cache.py::test_stale_schema_miss -x` | ❌ Wave 0 |
| PERF-03 | Threaded output == sequential output (determinism, no row loss) | integration | `pytest tests/test_concurrency.py::test_threaded_equals_sequential -x` | ❌ Wave 0 |
| PERF-03 | Per-row exception still isolated under the pool (one bad row, run continues) | integration | `pytest tests/test_concurrency.py::test_pool_isolates_bad_row -x` | ❌ Wave 0 |
| PERF-03 | `--workers N` wired from CLI → Config | unit | `pytest tests/test_concurrency.py::test_workers_flag -x` | ❌ Wave 0 |
| (regression) | All 162 prior tests stay green (scores unchanged) | full | `python3 -m pytest -q` | ✅ exists |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_cache.py tests/test_concurrency.py -x -q`
- **Per wave merge:** `python3 -m pytest -q` (full 162 + new must stay green)
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual confirm a real `--limit 4` run still produces an identical output sheet vs Phase 4.

### Wave 0 Gaps
- [ ] `tests/test_cache.py` — covers PERF-01 (round-trip, atomic/corrupt tolerance, key stability, schema version, `--no-cache`)
- [ ] `tests/test_concurrency.py` — covers PERF-03 (threaded==sequential, ordering, exception isolation, workers flag) + PERF-01 resumability
- [ ] No framework install needed — pytest already in use.
- [ ] Reuse `make_fetch_result` / network block from existing `conftest.py`; add a shared `tmp_cache_dir` fixture that calls `cache.set_cache_dir(tmp_path)` (consider adding to conftest so every test is isolated from the real `cache/`).

## Security Domain

> `security_enforcement` not set to false in config → included. This phase is local file I/O + threading; no auth/session/network-surface changes.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in this phase (no keys until Phase 6 PageSpeed) |
| V3 Session Management | no | CLI, no sessions |
| V4 Access Control | no | Local single-user tool |
| V5 Input Validation | partial | Cache `get` tolerates malformed JSON (treats as miss); `from_dict` defensive against missing keys |
| V6 Cryptography | no | SHA-256 used only as a non-security hash for cache filenames — not a security control; no secrets hashed |
| V7 Error Handling | yes | Cache read errors swallowed → miss; per-row boundary preserved; no stack traces to user |

### Known Threat Patterns for {stdlib file cache + threads}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Corrupt/poisoned cache file crashes next run | Denial of Service | `get()` catches `JSONDecodeError`/`OSError` → miss + re-fetch (PITFALLS.md #11) |
| Cached scraped HTML committed to git (data leak) | Information Disclosure | `cache/` already in `.gitignore` (verified); §6 keep-local |
| Path traversal via cache key | Tampering | Key is a SHA-256 hexdigest (only `[0-9a-f]`) → cannot escape cache dir |
| Race on concurrent same-key write | Tampering | `threading.Lock` around write; `os.replace` atomic; one file per URL |
| Logging full scraped HTML / PII | Information Disclosure | Log keys/scores, not cached HTML bodies (PITFALLS.md security table) |

## Sources

### Primary (HIGH confidence)
- Codebase: `lead_analyzer/{fetch,pipeline,models,config,cli}.py`, `tests/conftest.py`, `.gitignore` — actual seams, the cacheable `FetchResult`, existing per-row boundary, network-block fixture [VERIFIED this session]
- `.planning/research/ARCHITECTURE.md` — Pattern 1 (ThreadPoolExecutor), Pattern 2 (cache-aside per-URL atomic incremental), "cache sits under fetch", anti-patterns 1/3
- `.planning/research/PITFALLS.md` — #11 (partial-write corruption), #12 (stale cache / key collision), #10 (sort drops rows), #18 (privacy/commit), technical-debt + performance tables
- `.planning/REQUIREMENTS.md` — PERF-01, PERF-03 wording and AC mapping
- CLAUDE.md — AC1, AC7, AC8 scope (AC8 PageSpeed backoff deferred to Phase 6), §6 privacy
- docs.python.org — `os.replace` atomicity guarantee; `concurrent.futures.ThreadPoolExecutor` / `as_completed` [CITED]

### Secondary (MEDIUM confidence)
- Python 3.14.3 confirmed via `python3 --version` (stdlib availability) [VERIFIED]

### Tertiary (LOW confidence)
- None. All claims grounded in codebase or stdlib docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure stdlib, versions confirmed, zero new deps
- Architecture (cache placement under fetch, concurrency at run): HIGH — directly from ARCHITECTURE.md + verified seams
- Pitfalls: HIGH — mapped from PITFALLS.md #11/#12/#10 + verified against current code
- Default workers politeness (A1): LOW — assumption, flagged for confirmation

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable stdlib patterns; only changes if FetchResult shape or fetch seam changes)
