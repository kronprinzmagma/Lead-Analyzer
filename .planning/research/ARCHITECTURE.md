# Architecture Research

**Domain:** Local Python CLI batch enricher — Excel/CSV in → same table + 2 integer score columns out, with per-URL live website analysis, optional PageSpeed/LLM, caching, retry/backoff, graceful degradation.
**Researched:** 2026-06-14
**Confidence:** HIGH (standard-library + well-known small-library patterns; no novel/uncertain tech)

## Standard Architecture

This is a **batch pipeline / fan-out-fan-in** tool, not a service. The canonical shape for "table in → enrich each row concurrently → table out" is:

1. A thin **CLI/entrypoint** that parses args and calls one `run()` function.
2. An **orchestrator** that reads rows, fans them out across a thread pool, collects results, sorts, writes.
3. Per-row **analyzers** (pure-ish functions: signals in → verdict out) behind a shared **fetch + cache** layer.
4. A **scoring/aggregation** layer that turns raw signals into the two 1–5 integers + reason strings.

The key architectural force is **graceful degradation + resumability**: every layer must produce *some* verdict (with a reason) even when the network, an API key, or an LLM is missing, and a kill -9 mid-run must not throw away completed work.

### System Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                          CLI / Entrypoint (cli.py)                      │
│   argparse: input, output, --limit, --no-pagespeed, --no-llm,          │
│             --workers N, --no-cache, --csv                             │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ Config object
┌───────────────────────────────▼───────────────────────────────────────┐
│                         Orchestrator (pipeline.py)                      │
│   read rows → ThreadPoolExecutor(map analyze_row) → collect →          │
│   stable sort → write output                                           │
└───┬───────────────┬────────────────┬───────────────┬──────────────────┘
    │               │                │               │
┌───▼────┐   ┌──────▼───────┐  ┌─────▼────────┐  ┌───▼────────────┐
│ table  │   │  per-row      │  │   scoring    │  │  reasons /     │
│  io    │   │  analyzers    │  │  aggregation │  │  run-log       │
│ (read/ │   │  (6 dims +    │  │ (signals →   │  │  (AC6/AC11)    │
│ write/ │   │  payment)     │  │  1–5 + why)  │  │                │
│ urlcol)│   └──┬────────┬───┘  └──────────────┘  └────────────────┘
└────────┘      │        │
        ┌───────▼──┐  ┌──▼──────────┐
        │  fetch   │  │ pagespeed   │      ┌──────────────────────────┐
        │ (HTTP +  │  │  client     │      │   cache (JSON per URL,    │
        │ retry/   │  │ (optional)  │◄────►│   written incrementally)  │
        │ backoff) │  └─────────────┘      │   AC7 resumability        │
        └────┬─────┘  ┌─────────────┐      │   AC8 dedup API calls     │
             │        │  llm layer  │◄────►└──────────────────────────┘
             │        │ (optional)  │
             │        └─────────────┘
        ┌────▼─────────────────────┐
        │  payment data sources     │
        │ (legal form from name,    │
        │  branche table, optional  │
        │  Zefix/web — degradable)  │
        └───────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `cli.py` | Parse args, build `Config`, call `run()`. Exactly one command. | `argparse`, `if __name__ == "__main__"` + `console_scripts` entry point |
| `pipeline.py` (orchestrator) | Read → fan out over thread pool → collect → sort → write. Owns lifecycle, progress, top-level error handling. | `concurrent.futures.ThreadPoolExecutor`, `as_completed` |
| `table_io.py` | Read xlsx/csv into list of row-dicts **preserving column order**; tolerant URL-column detection; write output with original columns + 2 score cols. | `openpyxl` (xlsx), `csv` stdlib. No pandas (per constraints). |
| `fetch.py` | URL normalization (add scheme/`www`, validate), HTTP GET with timeout, retry + exponential backoff, capture status/redirects/headers/HTML. | `requests` + manual retry loop or `urllib3.Retry` |
| `analyzers/` | One module per Bedarf dimension (1–6) + one for Zahlungskräftigkeit. Each: raw signals → `DimensionVerdict(ok/gap/severe, reason)`. | `bs4` HTML parse, regex, header inspection |
| `pagespeed.py` | Optional client for PageSpeed-Insights API (dims 3–4). Returns None/degraded verdict when no key or error. | `requests`; keyless or `PAGESPEED_API_KEY` |
| `llm.py` | Optional qualitative layer for dim 6 / payment hints. No-op when no key. **After** deterministic checks. | Anthropic/OpenAI SDK or `requests` |
| `payment.py` | Estimate Zahlungskräftigkeit from legal form (parsed from name), Branche, website signals; optional Zefix/web lookup. Records source/assumption. | regex + lookup table + optional fetch |
| `cache.py` | Read/write per-URL JSON cache; key = normalized URL; written incrementally after each row. | `json` files in `cache/` dir, atomic write, thread lock |
| `scoring.py` | Aggregate dimension verdicts → integer 1–5 (both scores) per the rubric; "no website overrides to 5". | pure functions, deterministic |
| `reasons.py` / logging | Build per-row reason strings (which dims/signals drove score) + write run-log file. | stdlib `logging`, string builder |
| `models.py` | Dataclasses carrying data through the pipeline (see Data Flow). | `@dataclass` |

## Recommended Project Structure

```
lead_analyzer/
├── __init__.py
├── cli.py                  # argparse, entry point, builds Config, calls run()
├── config.py              # Config dataclass + .env loading (graceful, keys optional)
├── pipeline.py            # orchestrator: read → fan out → collect → sort → write
├── models.py              # RowRecord, FetchResult, DimensionVerdict, RowResult
├── table_io.py            # read/write xlsx+csv, tolerant URL-column detection
├── fetch.py               # normalize URL, HTTP GET, retry/backoff/timeout
├── cache.py               # per-URL JSON cache, incremental + thread-safe
├── scoring.py             # aggregate verdicts → 1–5 ints + override rules
├── reasons.py             # build reason strings for output column(s)
├── analyzers/
│   ├── __init__.py
│   ├── existence.py       # Dim 1: reachable? parked? social-only?
│   ├── technical.py       # Dim 2: HTTPS/SSL, own domain vs free subdomain
│   ├── performance.py     # Dim 3: viewport meta + PageSpeed (via pagespeed.py)
│   ├── seo.py             # Dim 4: title/meta/canonical/robots/headings
│   ├── ai_readiness.py    # Dim 5: JSON-LD/Schema.org, OG tags
│   ├── content.py         # Dim 6: contact/impressum/recency proxy (+ optional LLM)
│   └── payment.py         # Zahlungskräftigkeit estimator
├── clients/
│   ├── pagespeed.py       # optional PageSpeed-Insights client
│   └── llm.py             # optional LLM client (no-op without key)
└── logging_setup.py       # run-log file + console handler

run.py  (or `pyproject` console_scripts: lead-analyzer = lead_analyzer.cli:main)
cache/                     # gitignored JSON cache (created at runtime)
output/                    # gitignored outputs
data/sample_input.xlsx
.env                       # gitignored, optional API keys
```

### Structure Rationale

- **`analyzers/` as a package, one file per dimension:** each dimension is independently testable and independently degradable (dim 3 can fall back to heuristic without touching dim 4). Maps 1:1 to AC11's six dimensions, which makes traceability trivial — the verdict objects come pre-labelled by source module.
- **`clients/` separate from `analyzers/`:** PageSpeed and LLM are *optional I/O sources*, not scoring logic. Keeping them apart lets `performance.py` decide "use PageSpeed if available, else viewport heuristic" without the analyzer owning HTTP/key concerns.
- **`fetch.py` + `cache.py` as a shared lower layer:** every analyzer that needs the page reuses ONE fetch result per URL (fetch once, parse many). The cache sits under fetch so a cache hit skips both HTTP and PageSpeed.
- **`scoring.py` and `reasons.py` are pure:** no I/O. Given verdicts they produce the same ints and strings every time → testable, deterministic, satisfies "transparency over elegance."
- **Flat-ish, single package:** this is a CLI of a few hundred lines per area, not a service. Resist over-layering.

## Architectural Patterns

### Pattern 1: Fan-out / Fan-in over rows (ThreadPoolExecutor)

**What:** Orchestrator submits `analyze_row(record, config)` for every row to a thread pool, then collects results as they complete. I/O-bound work (HTTP, PageSpeed) overlaps; the GIL is irrelevant because threads block on network.
**When to use:** Hundreds of independent rows, each dominated by network latency. Exactly this tool.
**Trade-offs:** Simple and stdlib-only. Must make shared state (cache, log) thread-safe. `--workers` defaults to e.g. 8–16; keep modest to respect remote-site politeness and API rate limits.

**Example:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run(config):
    rows = table_io.read_rows(config.input)          # preserves order + columns
    url_col = table_io.detect_url_column(rows)        # tolerant; raise if none
    if config.limit:
        rows = rows[:config.limit]                    # --limit N for tiny E2E demo

    results = [None] * len(rows)
    with ThreadPoolExecutor(max_workers=config.workers) as pool:
        futures = {pool.submit(analyze_row, i, r, url_col, config): i
                   for i, r in enumerate(rows)}
        for fut in as_completed(futures):
            i = futures[fut]
            results[i] = fut.result()                 # analyze_row never raises (AC4)
    ordered = scoring.stable_sort(results)            # sort copy, original index kept
    table_io.write(config.output, rows, ordered, config)
```

### Pattern 2: Cache-aside, keyed by normalized URL, written incrementally (AC7 + AC8)

**What:** Before any network call for a URL, check `cache/<hash-of-normalized-url>.json`. On miss, fetch + analyze, then write the cache entry immediately (not at end of run). A re-run reads the cache and skips completed URLs.
**When to use:** Whenever an abort must not lose work and identical URLs (or repeated runs) must not re-hit rate-limited APIs.
**Trade-offs:** One small file per URL is the most crash-safe (each write is independent and atomic via temp-file + `os.replace`). A single big JSON is simpler but a mid-write crash can corrupt the whole cache — avoid. Cache the *raw signals / verdicts*, not the final score, so scoring tweaks don't force a re-crawl.

**Example:**
```python
def analyze_row(idx, row, url_col, config):
    url = fetch.normalize(row.get(url_col))
    if not url:                                        # empty URL edge-case
        return RowResult(idx, bedarf=5, zahl=payment.estimate(row),
                         reason="keine Website")
    key = cache.key_for(url)
    cached = None if config.no_cache else cache.get(key)
    if cached:
        signals = FetchResult.from_dict(cached)
    else:
        signals = fetch.get(url, config)              # retry/backoff/timeout, never raises
        cache.put(key, signals.to_dict())             # incremental, atomic, thread-safe
    verdicts = [m.analyze(signals, config) for m in DIMENSION_ANALYZERS]
    bedarf = scoring.bedarf(verdicts, signals)        # "no reachable site" → 5
    zahl   = payment.estimate(row, signals, config)
    return RowResult(idx, bedarf, zahl,
                     reason=reasons.build(verdicts, zahl.reason))
```

### Pattern 3: Optional-source with degradation contract

**What:** Optional sources (PageSpeed, LLM, Zefix) expose `is_available()` and return either a real verdict or a `degraded` verdict carrying a reason ("PageSpeed übersprungen: kein Key"). Analyzers never crash on a missing source; the reason string records the degradation so the score stays explainable.
**When to use:** Any capability gated on a key/network that AC4/AC9 say must not be required.
**Trade-offs:** Slightly more plumbing (every optional call returns a tagged result), but it is the mechanism that makes "<5 min, runs with zero keys" and AC6 traceability both true at once.

**Example:**
```python
def analyze(signals, config):  # performance.py (Dim 3)
    if config.use_pagespeed and pagespeed.is_available():
        ps = pagespeed.score(signals.url)             # cached + retry/backoff
        if ps is not None:
            return DimensionVerdict(dim=3, level=ps.level,
                                    reason=f"PageSpeed mobile={ps.perf}")
    has_viewport = "viewport" in signals.html_meta
    return DimensionVerdict(dim=3,
        level="ok" if has_viewport else "gap",
        reason="Heuristik: viewport-meta " + ("vorhanden" if has_viewport else "fehlt"))
```

## Data Flow

### Per-row flow

```
RowRecord (original cells, original order, source index)
    │  normalize URL
    ▼
FetchResult  ── cache.get / fetch.get(retry,backoff) ──►  cache.put (incremental)
  status, final_url, redirects, headers, ssl_ok, html, parsed meta/links
    │  fan out to 6 dimension analyzers (+ payment)
    ▼
[DimensionVerdict × 6]   each: dim#, level∈{ok,gap,severe}, reason str, source
    │  scoring.bedarf(verdicts, signals)   +   payment.estimate(...)
    ▼
RowResult
  source_index, bedarf:int(1-5), zahl:int(1-5), reason:str, sort_key
    │  collect all → stable_sort(desc bedarf, desc zahl, then source_index)
    ▼
Output table = original columns (unchanged, original order)
             + "Website-Bedarf (1-5)" + "Zahlungskräftigkeit (1-5)"
             [+ optional "Begründung"]
```

### Carrier dataclasses (`models.py`)

```python
@dataclass
class RowRecord:
    index: int                 # original position — never lost
    cells: dict[str, object]   # ordered: original columns verbatim

@dataclass
class FetchResult:
    url: str; ok: bool; status: int | None
    final_url: str | None; redirected: bool; ssl_ok: bool
    headers: dict; html: str | None
    error: str | None          # populated on timeout/refused → drives "nicht erreichbar"

@dataclass
class DimensionVerdict:
    dim: int                   # 1..6
    level: str                 # "ok" | "gap" | "severe"
    reason: str                # human-readable, goes into log + reason col
    source: str                # "html" | "pagespeed" | "llm" | "heuristic-fallback"

@dataclass
class RowResult:
    index: int
    bedarf: int                # 1..5, never empty (AC2)
    zahl: int                  # 1..5, never empty
    reason: str
    verdicts: list[DimensionVerdict]   # kept for run-log traceability (AC6/AC11)
```

The `index` field is the single most important design detail for AC2/sort correctness: it travels untouched from read to write so the **stable sort never loses or scrambles original rows**, and output cells are emitted from `RowRecord.cells` so original columns are byte-identical.

### Key Data Flows

1. **Fetch-once-parse-many:** `fetch.py` produces one `FetchResult` per URL; all six dimension analyzers read from it. No analyzer issues its own HTTP except optional PageSpeed/LLM.
2. **Verdict → score → reason:** dimension verdicts are the *only* input to `scoring.bedarf`, and the *same* verdicts feed `reasons.build` and the run-log. One source of truth → score and explanation can never disagree (AC6/AC11).
3. **Degradation tagging:** `source` on each verdict records whether a real measurement or a fallback produced it, surfacing in the reason column / log.

## Concurrency, Caching & Resumability

| Concern | Approach |
|---------|----------|
| Parallelism | `ThreadPoolExecutor(max_workers=config.workers)`, default ~8. I/O-bound, so threads (not processes) are correct and stdlib-only. |
| Cache + concurrency | Cache writes guarded by a `threading.Lock`; reads are lock-free (file read). Atomic write = temp file + `os.replace`. One file per URL → no cross-row write contention. |
| Rate limits (AC8) | PageSpeed/LLM clients own a small token-bucket or a `Semaphore` capping concurrent API calls below worker count; on HTTP 429/5xx → exponential backoff with jitter, capped retries, then degrade (not crash). |
| Resumability (AC7) | Cache is written incrementally per URL. A re-run with the same input + cache skips already-fetched URLs and only re-scores/writes. Optionally a tiny `progress.jsonl` appended per finished row for visibility, but the per-URL cache alone satisfies AC7. |
| Crash safety | `analyze_row` wraps everything in try/except and returns a degraded `RowResult` (never raises) → one bad URL can't kill the pool (AC4). Atomic cache writes mean a kill mid-write leaves the previous good file intact. |
| Politeness | Keep `--workers` modest; live websites are third-party. Per-host concern is minor here (one URL per host typically) but worth a note. |

## Output Construction (AC2 + sort)

1. Read into `list[RowRecord]` preserving column order (openpyxl: first row = headers in order; build an ordered dict per row).
2. Compute results keyed by `index`.
3. **Sort a list of results** by `(-bedarf, -zahl, index)` — sorting results, not the original rows, and tie-breaking on original index makes it stable and loss-free.
4. Emit rows in sorted order: for each result, write `record.cells` verbatim, then append the two score columns (ints), optionally a `Begründung` column.
5. Write `.xlsx` via openpyxl by default; if `--csv`, also/instead write CSV via stdlib `csv`.
6. Never write to the input file; write to `output/` (gitignored).

Headers must be exactly `Website-Bedarf (1-5)` and `Zahlungskräftigkeit (1-5)` (per CLAUDE.md §3). Scores are written as integers so Excel sorts/filters numerically.

## Logging Strategy (AC6 traceability)

Two complementary channels, fed from the same `verdicts`:

- **Run-log file** (`logging` to `output/run-<timestamp>.log`): per row, one line per dimension verdict (`dim, level, source, reason`) plus the payment assumption and final scores. This is the authoritative "which signals drove the score" record (AC6/AC11/AC5).
- **Reason column** (optional but recommended `Begründung`): a compact one-line summary in the output itself (e.g. "kein HTTPS; nicht mobil; PageSpeed übersprungen; AG → Zahl 4"). Lives in the deliverable, so Sales sees the *why* without opening logs.

Both derive from `RowResult.verdicts` + `payment.reason`, so they cannot drift from the score. Use module-level loggers (`logging.getLogger(__name__)`) so log lines are tagged by analyzer.

## Suggested Build Order

Start with the **smallest runnable end-to-end slice**, then iterate quality/robustness — directly per CLAUDE.md §5 and AC10.

1. **E2E skeleton (no network):** `cli.py` (argparse: input, output, `--limit`) → `table_io.read_rows` + `detect_url_column` → trivial `scoring` that returns constant `bedarf=3, zahl=3` → `table_io.write` xlsx with the two columns appended and stable sort. **Verify against `data/sample_input.xlsx --limit 4`.** Now Excel-in/Excel-out works. (AC2, AC9 shell)
2. **Models + fetch + existence (Dim 1):** add `models.py`, `fetch.py` (normalize + GET + timeout + try/except), and `analyzers/existence.py`. Wire real Dim-1 verdict; empty/broken URL → bedarf 5 with reason. Now the two sample edge-cases (empty URL Kiosk, broken `htp://…`) score sensibly. (AC4)
3. **Cache + concurrency:** add `cache.py` (per-URL JSON, atomic, incremental) and switch the orchestrator to `ThreadPoolExecutor`. Re-run skips cached URLs. (AC7, AC1 scale)
4. **Deterministic dimensions 2, 4, 5, 6 (HTML/header based):** technical, seo, ai_readiness, content analyzers + real `scoring.bedarf` aggregation + override "no reachable site → 5". Add reason column + run-log. (AC11 dims 1–4 measured, AC6)
5. **Payment estimator (Zahlungskräftigkeit):** legal-form-from-name + Branche table + website signals, with recorded assumption/source. (AC5)
6. **Optional PageSpeed (Dim 3) + rate limiting:** `clients/pagespeed.py` with availability check, backoff, `--no-pagespeed`. Degrades to viewport heuristic. (AC3 dim 3 real, AC8)
7. **Optional LLM layer (Dim 6 qualitative) + `--no-llm`:** runs only with a key, after deterministic checks.
8. **Hardening + README:** retry/backoff polish, `--workers`/`--no-cache` flags, full sample run, README setup <5 min, AC10 write-up of why sample scores are sensible.

Each step leaves a runnable tool; steps 1–3 form the GSD "tiny E2E first" milestone.

## Anti-Patterns

### Anti-Pattern 1: Sorting the original rows in place

**What people do:** sort the DataFrame / row list directly by score.
**Why it's wrong:** loses the original index, and unstable sorts scramble equal-score rows; risks dropping/duplicating rows (violates AC2 "Sortierung soll im Output nicht die Originalzeilen verlieren").
**Do this instead:** keep `index` on every record, sort a list of *results* with `(-bedarf, -zahl, index)`, emit original cells verbatim in that order.

### Anti-Pattern 2: One monolithic per-URL fetch inside every analyzer

**What people do:** each dimension re-requests the page.
**Why it's wrong:** 6× the HTTP traffic, breaks caching semantics, slow, rude to remote sites.
**Do this instead:** fetch once into `FetchResult`, pass it to all analyzers; only PageSpeed/LLM make their own (cached, rate-limited) calls.

### Anti-Pattern 3: Single giant cache file written at the end

**What people do:** accumulate results in memory, dump one big JSON at exit.
**Why it's wrong:** a crash/abort loses everything (violates AC7); a mid-write crash corrupts the whole cache.
**Do this instead:** per-URL JSON files written incrementally with atomic temp-file replace.

### Anti-Pattern 4: Hard-requiring API keys / network

**What people do:** raise/exit if `PAGESPEED_API_KEY` or an LLM key is absent.
**Why it's wrong:** breaks AC4/AC9 ("<5 min, runs without setup"), turns optional enrichment into a hard dependency.
**Do this instead:** optional-source degradation contract — `is_available()` gate, heuristic fallback, reason records the skip.

### Anti-Pattern 5: Letting one bad row kill the run

**What people do:** unhandled exception in an analyzer propagates out of the pool.
**Why it's wrong:** one malformed URL aborts a hundreds-row job (violates AC1/AC4).
**Do this instead:** `analyze_row` catches everything and returns a degraded `RowResult` with an error reason; the row still gets a score.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Target websites | `requests` GET, normalize scheme/www, timeout, retry/backoff, capture status+redirects+SSL+HTML | Third-party; be polite, modest concurrency, treat all errors as degraded verdicts |
| PageSpeed Insights API | Optional `clients/pagespeed.py`; keyless (strict limit) or `PAGESPEED_API_KEY`; semaphore + backoff on 429 | Dims 3–4 in one call; degrade to viewport/HTML heuristic when unavailable |
| LLM (Anthropic/OpenAI) | Optional `clients/llm.py`; runs only with key, after deterministic checks | Dim 6 qualitative + payment hints; never the sole basis for a score |
| Zefix / public company data | Optional within `payment.py`; legal form parsed from name is the zero-dependency baseline | Estimation must be flagged as estimation; no fabricated facts (AC5) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| orchestrator ↔ analyzers | direct call: `analyze_row(record, config)` | analyzers pure-ish, return `RowResult`; never raise |
| analyzers ↔ fetch/cache | `FetchResult` object | fetch-once-parse-many; cache-aside under fetch |
| analyzers ↔ clients (PageSpeed/LLM) | `is_available()` + tagged optional result | degradation contract |
| scoring/reasons ↔ verdicts | one shared `list[DimensionVerdict]` | single source of truth → score and explanation can't diverge |
| pipeline ↔ table_io | `list[RowRecord]` in, `(records, sorted results)` out | original columns/order preserved verbatim |

## Sources

- Python `concurrent.futures` (ThreadPoolExecutor / as_completed) — stdlib documentation; standard fan-out/fan-in pattern for I/O-bound batch work. (HIGH)
- `openpyxl` for xlsx read/write preserving column order; stdlib `csv` for CSV. (HIGH — matches project's installed deps)
- Cache-aside + atomic write (`os.replace` after temp file) — well-established crash-safe file-write idiom. (HIGH)
- Exponential backoff with jitter for rate-limited HTTP APIs — standard resilience pattern (e.g. `urllib3.Retry`, common backoff guidance). (HIGH)
- Project spec `CLAUDE.md` (AC1–AC11), `docs/scoring_website_bedarf.md` (6-dimension rubric), `.planning/PROJECT.md` (constraints: Python + openpyxl/requests/bs4, graceful degradation, JSON cache decision). (Authoritative for requirements)

---
*Architecture research for: local Python CLI batch lead-scoring tool*
*Researched: 2026-06-14*
