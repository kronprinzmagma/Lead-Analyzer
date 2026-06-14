# Phase 6: Optional PageSpeed (Dimension 3) + Rate Limiting — Research

**Researched:** 2026-06-14
**Domain:** Optional external API enrichment (Google PageSpeed Insights v5) for Dim 3, with rate limiting / budgeting / graceful degradation, in a fully-offline-testable Python CLI.
**Confidence:** HIGH (architecture, codebase integration, degradation contract, offline testability), MEDIUM (PSI keyless quota magnitude — irrelevant by design since we recommend default-OFF-without-key).

## Summary

Phase 6 replaces exactly one line in the pipeline — `scoring.DIM3_PLACEHOLDER` — with a real Dimension-3 verdict produced by a new pure analyzer `analyzers/performance.py`. The analyzer ALWAYS derives a baseline verdict from the viewport-meta tag already present in `fr.html` (parse-once `soup`), and OPTIONALLY refines it with a Lighthouse performance score when a PageSpeed result is available. A new optional client `clients/pagespeed.py` performs the network call, returns a small dataclass or `None` (never raises), is gated by `is_available()`, is rate-limited by a semaphore + jittered backoff honoring `Retry-After`, is capped by a per-run call budget, and caches every result per-URL using the existing `cache.py` atomic-write pattern (separate namespace).

The single most important correctness property (Pitfall 8): **a PSI error / timeout / quota / non-200 / malformed-JSON must NEVER be scored as "slow site"** — it must fall back to the viewport heuristic, identical to "PSI was never attempted", carrying a `(PageSpeed übersprungen/Fehler)` note. This is guaranteed structurally by having the client return `None` on every failure and having the analyzer treat `None` and "not attempted" through the exact same code path.

**Primary recommendation:** PSI defaults to **OFF unless a key is present** (auto-detect `PAGESPEED_API_KEY`). With a key it is ON-but-budgeted. `--no-pagespeed` always forces off. This satisfies AC9 (`<5 min`, zero-setup run is fully offline, viewport heuristic already satisfies "Dim 3 measured at HTML level" per AC11) AND lets a keyed run measure real Lighthouse scores. Load `.env` via a tiny stdlib KEY=VALUE parser in `config.py` (no new dependency — python-dotenv is NOT installed; adding it would contradict the zero-new-dep stance and is unnecessary).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Viewport-meta detection (baseline Dim 3) | Per-row analyzer (`performance.py`, pure) | — | Reads existing parse-once `soup`/`fr.html`; no I/O; always available offline |
| Lighthouse perf/LCP/CLS/TBT refinement | Optional client (`clients/pagespeed.py`) | analyzer consumes result | External I/O + key/quota concerns belong in a client, not in scoring logic (ARCHITECTURE.md) |
| Rate limiting / backoff / budget | Optional client (`clients/pagespeed.py`) | orchestrator owns the shared semaphore/budget instance | PSI concurrency must be capped BELOW fetch-worker count, independent of the ThreadPoolExecutor |
| PSI result persistence | `cache.py` (existing, reused) | client calls it | AC7/AC8: re-runs/aborts must not re-call PSI |
| `.env` key loading | `config.py` | `cli.py` triggers it | Capability flag derives from key presence; one place to load |
| Skip decision (`--no-pagespeed`, no key) | `cli.py` → `Config` → `is_available()` | analyzer reads `config.use_pagespeed` | Degradation contract gate |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.34.2 (installed) | PSI v5 GET | Already the project HTTP client; `Session` + tuple timeout already used in `fetch.py` [VERIFIED: codebase fetch.py] |
| json (stdlib) | — | Parse PSI response + cache + `.env`-adjacent | Already used everywhere [VERIFIED: codebase] |
| threading.Semaphore / Lock (stdlib) | — | Cap concurrent PSI calls; shared call-budget counter | `cache.py` already uses `threading.Lock`; same pattern [VERIFIED: codebase cache.py] |
| random (stdlib) | — | Jitter for backoff | Standard backoff hygiene |
| beautifulsoup4 | 4.15.0 (installed) | viewport-meta extraction (reuses existing `soup`) | Already the parse-once tree in `pipeline.analyze_row` [VERIFIED: codebase pipeline.py L52] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| — | — | — | No new libraries. `.env` loading via ~12-line stdlib parser. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `.env` parser | python-dotenv 1.2.2 | dotenv is the convention but is NOT installed [VERIFIED: `.venv/bin/python -c "import dotenv"` → ModuleNotFoundError]; adding it breaks the zero-new-dep stance for a 12-line parse. Reject. |
| `threading.Semaphore` | `urllib3.Retry` adapter on a Session | Retry adapter handles per-request backoff but NOT a cross-row concurrency cap or a per-run call budget. We need both → manual semaphore + budget + small backoff loop. Optionally combine: Retry for `Retry-After` on the adapter PLUS semaphore+budget around the call. Recommend a self-contained manual loop for full control + testability (no real sleeps in tests). |
| Separate ThreadPoolExecutor for PSI | Semaphore shared inside existing pool | A second pool complicates ordering and the per-row cache flow. A semaphore acquired inside `analyze_row` (via the analyzer/client) caps PSI concurrency while keeping ONE pool. Recommend semaphore. |

**Installation:**
```bash
# No installation. All stdlib + already-installed requests/bs4.
```

**Version verification:** No new packages. `requests` 2.34.2, `beautifulsoup4` 4.15.0, `pytest` 9.1.0 verified installed on 2026-06-14 [VERIFIED: `.venv/bin/pip` / `pytest --version`].

## Architecture Patterns

### System Architecture Diagram

```
analyze_row(record, url_col, config)              [pipeline.py — existing]
  │ normalize → fetch() (cache-aside, never raises) → soup = parse-once
  ▼
verdicts = [
  existence.analyze(fr, soup),     # Dim 1
  technical.analyze(fr),           # Dim 2
  performance.analyze(fr, soup, ps_result),   # Dim 3  ← REPLACES DIM3_PLACEHOLDER
  seo.analyze(fr, soup),           # Dim 4
  ai_readiness.analyze(soup),      # Dim 5
  content.analyze(fr, soup),       # Dim 6
]
                         ▲
                         │ ps_result (PsResult | None)
        ┌────────────────┴───────────────────────────────────┐
        │ ps_result = None                                    │
        │ if config.use_pagespeed and client.is_available():  │
        │     ps_result = client.score(fr.final_url or fr.url)│  ← may be None on ANY failure
        └────────────────┬───────────────────────────────────┘
                         ▼
   clients/pagespeed.py  PageSpeedClient
     is_available()        → key present (recommended) OR keyless-allowed flag
     score(url) -> PsResult | None
        │ 1. cache.get(ps_key) → hit? return cached PsResult        (AC7/AC8)
        │ 2. budget.try_consume() → exhausted? return None (skip)   (PERF-02)
        │ 3. with semaphore:  (cap concurrency < workers)           (AC8)
        │      GET pagespeedonline.googleapis.com/.../runPagespeed
        │      strategy=mobile&category=performance&category=seo[&key=]
        │      timeout=(connect, read)                              (Pitfall 2)
        │      429/5xx → backoff(Retry-After + jitter), capped retries
        │      any error / non-200 / parse fail / quota → return None  ← NEVER raise
        │ 4. parse lighthouseResult.categories.performance.score + audits
        │ 5. cache.put(ps_key, PsResult)                            (AC7/AC8)
        ▼
   PsResult(perf_score, lcp_ms, cls, tbt_ms, ok=True)  OR  None
```

### Recommended Project Structure
```
lead_analyzer/
├── analyzers/
│   └── performance.py        # NEW — Dim 3: viewport baseline + PSI refinement (pure)
├── clients/
│   ├── __init__.py           # NEW (package)
│   └── pagespeed.py          # NEW — optional PSI client: is_available(), score()->PsResult|None
├── config.py                 # EDIT — add .env loader; pagespeed fields; key from env
├── cli.py                    # EDIT — add --no-pagespeed flag; trigger .env load
├── pipeline.py               # EDIT — build performance verdict; instantiate client once in run()
├── cache.py                  # REUSE — add a namespaced key helper for PSI (or key suffix)
└── models.py                 # EDIT — add PsResult dataclass (small, JSON-serializable)
tests/
├── test_performance.py       # NEW — analyzer: viewport ± ps_result ± None
├── test_pagespeed_client.py  # NEW — mock requests: 200/429+Retry-After/timeout/malformed→None; budget; semaphore
└── test_env_loader.py        # NEW — .env parse: comments/blank/quotes/no-override
```

### Pattern 1: Optional-source degradation contract (the core pattern)
**What:** The client exposes `is_available()` and `score(url) -> PsResult | None`. The analyzer NEVER calls the network directly; it receives a result-or-None and treats `None` exactly like "not attempted".
**When to use:** Any capability gated on a key/network that AC4/AC9 forbid as a hard dependency.
**Example:**
```python
# Source: ARCHITECTURE.md Pattern 3 (adapted to this codebase's signatures)

# pipeline.run(): construct ONE client (shared semaphore + budget) for the whole run
ps_client = pagespeed.PageSpeedClient.from_config(config)   # None if disabled

# pipeline.analyze_row(): gate + call, never raise
ps_result = None
if ps_client is not None and ps_client.is_available():
    ps_result = ps_client.score(fr.final_url or fr.url)     # PsResult | None — never raises
verdicts = [
    existence.analyze(fr, soup),
    technical.analyze(fr),
    performance.analyze(fr, soup, ps_result),               # ← replaces DIM3_PLACEHOLDER
    seo.analyze(fr, soup),
    ai_readiness.analyze(soup),
    content.analyze(fr, soup),
]
```

### Pattern 2: PSI-error-is-not-slow (the inversion guard)
**What:** `performance.analyze` branches on `ps_result is None` FIRST, returning the viewport-only verdict. Only a real `PsResult` with `ok=True` ever produces a perf-driven `gap`/`severe`. There is no code path where a failed PSI lowers the score below the viewport baseline.
**Example:**
```python
# analyzers/performance.py  (pure, offline-testable)
from ..models import DimensionVerdict

def analyze(fr, soup, ps_result=None) -> DimensionVerdict:
    """Dim 3 — viewport baseline, optional PSI refinement. PSI failure ≠ slow site."""
    has_viewport = _has_viewport_meta(soup)   # parse fr.html once already done upstream

    # --- PSI unavailable / failed / not attempted: viewport heuristic ONLY ---
    if ps_result is None:
        note = "(PageSpeed übersprungen/Fehler)"
        if has_viewport:
            return DimensionVerdict(3, "ok", f"viewport-meta vorhanden {note}", "heuristic-fallback")
        return DimensionVerdict(3, "gap", f"kein viewport-meta {note}", "heuristic-fallback")

    # --- real PSI result: refine. Worst of (viewport, lighthouse bands) ---
    level = _band_from_lighthouse(ps_result)          # ok/gap/severe from perf+LCP+CLS+TBT
    if not has_viewport:
        level = _worse(level, "gap")                  # missing viewport is at least a gap (FEATURES.md)
    return DimensionVerdict(
        3, level,
        f"PageSpeed mobile perf={ps_result.perf_score:.2f}"
        + ("" if has_viewport else "; kein viewport-meta"),
        "pagespeed",
    )
```

### Pattern 3: Lighthouse band mapping (FEATURES.md thresholds, verified)
```python
# Source: FEATURES.md Dim 3 table — [CITED: Google PSI v5 docs response shape]
def _band_from_lighthouse(r) -> str:
    bands = []
    # performance score 0..1
    if r.perf_score is not None:
        bands.append("ok" if r.perf_score >= 0.90 else "gap" if r.perf_score >= 0.50 else "severe")
    if r.lcp_ms is not None:
        bands.append("ok" if r.lcp_ms <= 2500 else "gap" if r.lcp_ms <= 4000 else "severe")
    if r.cls is not None:
        bands.append("ok" if r.cls <= 0.10 else "gap" if r.cls <= 0.25 else "severe")
    if r.tbt_ms is not None:
        bands.append("ok" if r.tbt_ms <= 200 else "gap" if r.tbt_ms <= 600 else "severe")
    if not bands:
        return "ok"          # PSI answered but no usable metric → don't penalize
    order = {"ok": 0, "gap": 1, "severe": 2}
    return max(bands, key=lambda b: order[b])   # worst metric wins (consistent with "more gap = more Bedarf")
```

### Pattern 4: PSI endpoint + response parse (verified shape)
```python
# Source: STACK.md / FEATURES.md — [CITED: developers.google.com PSI v5]
ENDPOINT = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
params = {"url": url, "strategy": "mobile",
          "category": ["performance", "seo"]}      # requests encodes list → repeated param
if key:
    params["key"] = key
# parse:
lr = data["lighthouseResult"]
perf = lr["categories"]["performance"]["score"]                       # 0..1
lcp  = lr["audits"]["largest-contentful-paint"]["numericValue"]       # ms
cls  = lr["audits"]["cumulative-layout-shift"]["numericValue"]
tbt  = lr["audits"]["total-blocking-time"]["numericValue"]            # ms
# EVERY access wrapped: any KeyError/TypeError → return None (treat as "PSI failed")
```
> Note: FEATURES.md cites the host `www.googleapis.com/pagespeedonline/...`; STACK.md cites `pagespeedonline.googleapis.com/pagespeedonline/...`. Both are Google-served aliases for PSI v5. [ASSUMED] both resolve; the canonical current host is `pagespeedonline.googleapis.com`. Tests mock the call so the exact host is not load-bearing for the suite; confirm with one live probe during README/AC9 work if a key is wired.

### Anti-Patterns to Avoid
- **PSI as a hard dependency / inline mandatory call** (Pitfall 8): turns a 400-row run into hours and aborts on 429. → Optional, post-pass, budgeted, skippable.
- **Scoring a PSI error/timeout as "slow" (`severe`)** (Pitfall 8/9): inverts the score. → `None` → viewport baseline only.
- **Raising from the client** (Pitfall 1): one PSI failure must not enter the per-row exception path as a crash. → `score()` returns `None` on every failure.
- **Unbounded retries** (Performance trap): a flaky host with repeated 429 never finishes. → capped retries (e.g. 3) then degrade.
- **Re-calling PSI on every re-run** (AC7/AC8): → cache every `PsResult` per-URL (separate namespace) so re-runs/aborts skip the call.
- **Concurrency = worker count for PSI** (AC8): blasting 8 PSI calls trips quota. → semaphore caps PSI concurrency to 2 (below `--workers`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic per-URL PSI cache | New cache file format | Existing `cache.py` (`key_for`, `get`, `put`, atomic `os.replace`, schema-versioned, thread-safe) | Already battle-tested for FetchResult; just namespace the key (e.g. `"ps:" + url` → `cache.key_for(["ps", url])`) so PSI and fetch entries never collide |
| Thread-safe writes | New lock | `cache.py` module `_LOCK` already serializes writes | Reuse |
| HTTP timeout/session | Raw socket | `requests.Session` + tuple timeout, as in `fetch.py` | Same proven config |
| `.env` parsing | python-dotenv (new dep) | ~12-line stdlib KEY=VALUE parser | Zero new deps; AC9 only needs key loading, not dotenv's full feature set |
| Concurrency primitive | Custom token bucket | `threading.Semaphore(n)` | stdlib, trivially testable (no sleeps) |

**Key insight:** Everything Phase 6 needs (atomic cache, thread lock, requests session, timeout discipline) already exists in the codebase from Phases 2 and 5. Phase 6 is overwhelmingly *wiring + one new pure analyzer + one new optional client*, not new infrastructure.

## Common Pitfalls

### Pitfall 1: PSI error scored as "slow site" (score inversion)
**What goes wrong:** A 429/timeout/parse-failure is interpreted as bad performance → Dim 3 `severe` → Bedarf inflated → a fine site ranks as a top lead.
**Why it happens:** Treating "no PSI data" and "PSI says slow" as the same branch.
**How to avoid:** Client returns `None` on ALL failures. Analyzer's `if ps_result is None:` branch is identical to "PSI never attempted" — viewport-only, never below baseline. Golden test: `analyze(fr_with_viewport, soup, ps_result=None)` → `ok`, NOT `severe`.
**Warning signs:** Bedarf scores swing upward when PSI is enabled; many Dim 3 `severe` with `source="pagespeed"` on sites that load fine.

### Pitfall 2: Run takes hours / 429 storm
**What goes wrong:** PSI is ~3–30s/call; 8 concurrent calls + keyless quota → 429 burst, unbounded wall time.
**How to avoid:** Semaphore cap (2), per-run budget cap, capped jittered backoff honoring `Retry-After`, cache hits skip the call, default-OFF-without-key.
**Warning signs:** "sometimes takes 20 min", bursts of 429.

### Pitfall 3: PSI cache key collides with fetch cache
**What goes wrong:** Same `cache.key_for([url])` used for both → a fetch entry overwrites/serves as a PSI entry.
**How to avoid:** Namespace the PSI key: `cache.key_for(["pagespeed-v1", strategy, url])`. The schema_version in `cache.py` already guards format; the namespace token guards purpose.
**Warning signs:** PSI returns a FetchResult-shaped dict; JSON schema mismatch on read.

### Pitfall 4: Monotonicity break when replacing the placeholder
**What goes wrong:** `DIM3_PLACEHOLDER` contributes 0 gap-points (`level="ok"`). A real verdict that returns `gap`/`severe` adds points and could push otherwise-fine sites into a higher Bedarf band, OR require re-tuning bands.
**How to avoid:** The aggregation in `scoring.bedarf` is ALREADY monotonic by construction (`G` = sum of gap points, tie-break `max(g_score, s_score)`) — adding a Dim-3 gap can only raise or hold the score, never lower it [VERIFIED: codebase scoring.py L36-42]. Do NOT change bands. A viewport-present site still yields Dim 3 = `ok` (0 points) in the default no-key run, so existing fixtures' Bedarf values are unchanged when PSI is off. Confirm: in the offline default path, `performance.analyze(fr, soup_with_viewport, None)` returns `ok` ⇒ same G as the placeholder ⇒ identical Bedarf ⇒ all 177 tests stay green.
**Warning signs:** `test_scoring_bedarf` / `test_pipeline_bedarf` regressions after the swap.

### Pitfall 5: PSI called with the wrong URL (pre-redirect)
**What goes wrong:** Calling PSI on the raw candidate instead of `final_url` wastes a redirect and may 404.
**How to avoid:** Pass `fr.final_url or fr.url`. Skip PSI entirely when `not fr.ok` or `fr.html is None` (no point PageSpeed-ing an unreachable/blocked host — Dim 1 already drives those).

### Pitfall 6: `.env` loader overrides real environment
**What goes wrong:** A loader that always sets `os.environ[k]=v` clobbers a key the user exported in their shell.
**How to avoid:** `os.environ.setdefault(k, v)` (don't override existing). Ignore comments (`#`), blank lines, and strip surrounding quotes.

## Code Examples

### Tiny stdlib .env loader (in config.py)
```python
# Source: stdlib only — replaces python-dotenv (not installed)
import os
from pathlib import Path

def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines into os.environ WITHOUT overriding existing vars. Never raises."""
    p = Path(path)
    if not p.exists():
        return
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)   # don't clobber a real env var
    except OSError:
        return
```

### Client availability + score skeleton
```python
# clients/pagespeed.py
import os, random, time
import requests
from .. import cache
from ..models import PsResult

ENDPOINT = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"

class PageSpeedClient:
    def __init__(self, key, semaphore, budget, timeout, sleep=time.sleep):
        self._key = key; self._sem = semaphore; self._budget = budget
        self._timeout = timeout; self._sleep = sleep   # sleep injected → tests pass a no-op

    @classmethod
    def from_config(cls, config):
        if not getattr(config, "use_pagespeed", False):
            return None
        key = os.environ.get("PAGESPEED_API_KEY")
        if not key:                       # recommended default: no key ⇒ disabled
            return None
        import threading
        return cls(key,
                   threading.Semaphore(getattr(config, "pagespeed_concurrency", 2)),
                   _Budget(getattr(config, "pagespeed_budget", 400)),
                   (config.timeout_connect, max(config.timeout_read, 30.0)))

    def is_available(self) -> bool:
        return self._key is not None and not self._budget.exhausted()

    def score(self, url):
        ck = cache.key_for(["pagespeed-v1", "mobile", url])
        cached = cache.get(ck)
        if cached is not None:
            return PsResult(**cached)              # cache hit: no network, no budget spend
        if not self._budget.try_consume():
            return None                            # budget exhausted → degrade
        data = self._request(url)                  # returns dict | None, never raises
        if data is None:
            return None
        res = _parse(data)                         # PsResult | None (defensive)
        if res is not None:
            cache.put(ck, res.__dict__)
        return res

    def _request(self, url):
        params = {"url": url, "strategy": "mobile",
                  "category": ["performance", "seo"], "key": self._key}
        for attempt in range(3):
            try:
                with self._sem:
                    r = requests.get(ENDPOINT, params=params, timeout=self._timeout)
            except requests.RequestException:
                return None                        # network/timeout → degrade
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    return None                    # malformed JSON → degrade
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                retry_after = _parse_retry_after(r.headers.get("Retry-After"))
                self._sleep(retry_after + random.uniform(0, 0.5) if retry_after
                            else (2 ** attempt) + random.uniform(0, 0.5))
                continue
            return None                            # any other status / exhausted retries → degrade
        return None
```

### PsResult dataclass (models.py)
```python
@dataclass
class PsResult:
    perf_score: float | None = None   # 0..1
    lcp_ms: float | None = None
    cls: float | None = None
    tbt_ms: float | None = None
    ok: bool = True                   # always True when constructed; None replaces "not ok"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CrUX field data (`loadingExperience.metrics`) as Dim-3 signal | Lighthouse LAB scores (`lighthouseResult.categories.performance.score` + audits) | Google phasing CrUX out of PSI | Use lab perf/LCP/CLS/TBT as primary; CrUX only as bonus-if-present, never primary [CITED: FEATURES.md / developers.google.com PSI about] |
| python-dotenv assumed | stdlib `.env` parser | This project (not installed) | Zero new deps |

**Deprecated/outdated:** Relying on CrUX category for low-traffic SME sites — it's usually empty for these targets. Lab scores always present in a successful PSI run.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Canonical PSI host is `pagespeedonline.googleapis.com` (both cited aliases resolve) | Pattern 4 | LOW — tests mock the call; verify with one live probe before AC9/README if a key is wired |
| A2 | Default-OFF-without-key is the right AC9 trade-off | Default behavior | LOW — viewport heuristic already satisfies AC11 "Dim 3 measured at HTML level"; product owner could prefer ON-but-budgeted with key. Both are supported by the same code; only `from_config` policy differs |
| A3 | PSI keyless quota is too low to be a reliable default | Default behavior | LOW — irrelevant since recommendation is key-gated; keyless not used |
| A4 | `read` timeout should be raised to ≥30s for PSI (Lighthouse runs are slow) | Client skeleton | LOW — a too-short read timeout just yields `None` → viewport fallback (safe), but wastes budget. 30–60s recommended |

## Open Questions

1. **PSI default: OFF-without-key vs ON-but-budgeted-with-key vs keyless-allowed?**
   - What we know: AC9 demands a zero-setup `<5 min` offline run; AC11 is satisfied by the viewport heuristic without PSI; PSI is slow + quota-limited.
   - What's unclear: whether the product owner wants PSI attempted keyless when no key is present.
   - Recommendation: **default OFF unless `PAGESPEED_API_KEY` present** (A2). `--no-pagespeed` always forces off. This is the safest AC9/AC8 posture and keeps all 177 tests' offline behavior byte-identical. Expose `pagespeed_concurrency` (2) and `pagespeed_budget` (400) as Config fields for tunability; a keyless opt-in (`--pagespeed-keyless`) can be added later without redesign.

2. **Where to call `load_dotenv()`?**
   - Recommendation: in `cli.main()` BEFORE building `Config` (so `Config.from_args` / `from_config` can read `os.environ`), OR a `Config.load_env()` classmethod. Single call site, never in analyzers.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| requests | PSI GET | ✓ | 2.34.2 | — |
| beautifulsoup4 | viewport-meta | ✓ | 4.15.0 | — |
| python-dotenv | `.env` load | ✗ | — | stdlib `.env` parser (recommended; no dep) |
| PAGESPEED_API_KEY | real Dim-3 perf | ✗ (env, optional) | — | viewport heuristic + note (AC11 still satisfied) |
| Network / PSI endpoint | real Dim-3 perf | ✗ at test time (blocked) | — | viewport heuristic; tests mock the client |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** python-dotenv → stdlib parser. PSI key/network → viewport heuristic (this IS the designed degradation, AC4/AC11).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 [VERIFIED] |
| Config file | none detected (pytest defaults; `tests/conftest.py` provides autouse network-block + cache-isolation) |
| Quick run command | `.venv/bin/python -m pytest tests/test_performance.py tests/test_pagespeed_client.py tests/test_env_loader.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest -q` (must stay ≥177 green + new) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BED-03 | viewport present + ps=None → `ok` (no PSI) | unit | `pytest tests/test_performance.py::test_viewport_present_no_psi_is_ok -x` | ❌ Wave 0 |
| BED-03 | viewport absent + ps=None → `gap` | unit | `pytest tests/test_performance.py::test_no_viewport_no_psi_is_gap -x` | ❌ Wave 0 |
| BED-03 | real PsResult perf<0.5 → `severe` (source=pagespeed) | unit | `pytest tests/test_performance.py::test_psi_low_perf_severe -x` | ❌ Wave 0 |
| BED-03 | real PsResult perf>=0.9 + viewport → `ok` | unit | `pytest tests/test_performance.py::test_psi_good_perf_ok -x` | ❌ Wave 0 |
| BED-03 | LCP/CLS/TBT worst-band wins | unit | `pytest tests/test_performance.py::test_worst_metric_band -x` | ❌ Wave 0 |
| PERF-02/AC8/AC4 | **ps_result=None must NOT be `severe`** (inversion guard) | unit | `pytest tests/test_performance.py::test_psi_error_not_scored_slow -x` | ❌ Wave 0 |
| PERF-02 | client `score()` returns None on timeout (mock RequestException) | unit | `pytest tests/test_pagespeed_client.py::test_timeout_returns_none -x` | ❌ Wave 0 |
| PERF-02 | 429 + Retry-After → backoff (injected sleep) then None after capped retries | unit | `pytest tests/test_pagespeed_client.py::test_429_retry_after_capped -x` | ❌ Wave 0 |
| PERF-02 | malformed JSON → None | unit | `pytest tests/test_pagespeed_client.py::test_malformed_json_none -x` | ❌ Wave 0 |
| PERF-02 | 200 valid → PsResult parsed correctly | unit | `pytest tests/test_pagespeed_client.py::test_200_parsed -x` | ❌ Wave 0 |
| PERF-02/AC8 | per-run budget exhausted → score() returns None without network | unit | `pytest tests/test_pagespeed_client.py::test_budget_exhausted_skips -x` | ❌ Wave 0 |
| PERF-02 | semaphore caps concurrency (≤2 in flight) | unit | `pytest tests/test_pagespeed_client.py::test_semaphore_caps -x` | ❌ Wave 0 |
| AC7/AC8 | second score() for same URL → cache hit, no network, no budget spend | unit | `pytest tests/test_pagespeed_client.py::test_cache_hit_no_network -x` | ❌ Wave 0 |
| PERF-02 | `is_available()` False when no key | unit | `pytest tests/test_pagespeed_client.py::test_unavailable_without_key -x` | ❌ Wave 0 |
| AC9 | `.env` parsed; comments/blank/quotes; no override of existing env | unit | `pytest tests/test_env_loader.py -x` | ❌ Wave 0 |
| BED-03 | `--no-pagespeed` → client is None, pipeline uses heuristic | unit/integration | `pytest tests/test_pipeline_bedarf.py::test_no_pagespeed_flag -x` | ❌ Wave 0 (extend existing) |
| BED-08 | monotonicity: offline default Bedarf unchanged after placeholder swap | regression | `pytest tests/test_scoring_bedarf.py tests/test_pipeline_bedarf.py -q` | ✅ existing (must stay green) |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_performance.py tests/test_pagespeed_client.py tests/test_env_loader.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest -q` (full suite, ≥177 + new, all green)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus a manual `--no-pagespeed` full-sample smoke run (AC9 offline) and, if a key is available, ONE keyed run on `--limit 2` to confirm live parse (not in the automated suite).

### Wave 0 Gaps
- [ ] `tests/test_performance.py` — Dim-3 analyzer, all viewport×PSI×None combinations + the inversion guard (BED-03, AC4/AC8)
- [ ] `tests/test_pagespeed_client.py` — mock `requests.get` for 200/429+Retry-After/timeout/malformed; budget; semaphore; cache hit; injected `sleep` no-op (PERF-02, AC7/AC8)
- [ ] `tests/test_env_loader.py` — stdlib `.env` parser (AC9)
- [ ] Extend `tests/test_pipeline_bedarf.py` — `--no-pagespeed` path + confirm offline Bedarf unchanged (BED-08 regression)
- [ ] Shared fixtures: a `make_ps_result(**overrides)` helper in conftest (mirrors `make_fetch_result`); a `monkeypatch.setattr(requests, "get", fake)` PSI mock pattern (conftest already supports per-test override of the autouse block)
- [ ] No framework install needed (pytest 9.1.0 present)

## Project Constraints (from CLAUDE.md)

- **AC4 / ROB-01/02/03:** No crash on any input; PSI error/timeout/quota must produce a sensible score + note, never abort. PSI error ≠ "slow". Per-row exception boundary already in `pipeline.analyze_row`.
- **AC8 / PERF-02:** External APIs use batching/retry/backoff, respect rate limits + `Retry-After`, per-run budget, skippable via flag; an API error doesn't abort the run.
- **AC9 / SETUP-01:** Single entry point; runs in `<5 min` with zero keys (offline); `.env` for keys; README explains setup. → PSI default OFF without key.
- **AC11 / BED-03:** Dim 3 measured — viewport always (HTML level), PageSpeed when available; without network/key → heuristic + note. Min. dims 1–4 really measured: viewport-meta IS a real HTML measurement, so Dim 3 stays "real" even offline.
- **AC7 / PERF-01:** PSI results cached incrementally (atomic, reuse `cache.py`); re-run/abort doesn't re-call.
- **§6:** `.env` and outputs never committed; PSI is local-only.
- **DIFF-02:** LLM layer (Dim 6 qualitative) stays OUT of this phase.
- **Constraint (test harness):** Network blocked in tests (autouse conftest); PSI client must be mockable; no real PSI call or real key in the suite.

## Sources

### Primary (HIGH confidence)
- Codebase: `scoring.py` (monotonic `bedarf`, `DIM3_PLACEHOLDER`), `pipeline.py` (analyze_row verdict list, ThreadPoolExecutor), `fetch.py` (Session+timeout pattern), `cache.py` (atomic per-URL JSON, `_LOCK`, schema_version, `key_for`), `config.py` (`use_pagespeed`, timeouts), `cli.py` (flag pattern), `models.py` (DimensionVerdict, FetchResult), `analyzers/technical.py`+`seo.py` (analyzer signature convention), `tests/conftest.py` (autouse network block + cache isolation + `make_fetch_result`) — [VERIFIED 2026-06-14]
- `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `REQUIREMENTS.md`, `docs/scoring_website_bedarf.md`, `CLAUDE.md` — authoritative project research/spec
- `.venv/bin/python -c "import dotenv"` → ModuleNotFoundError; `pytest --version` → 9.1.0; 177 tests collected — [VERIFIED 2026-06-14]

### Secondary (MEDIUM confidence)
- Google PSI v5 docs (response shape `lighthouseResult.categories.*.score`, `audits.*.numericValue`) — cited via FEATURES.md/STACK.md
- PSI keyless quota magnitude — MEDIUM (undocumented anonymous limit); mitigated by key-gated default

### Tertiary (LOW confidence)
- Exact canonical PSI host alias — A1, verify with a live probe before AC9 if a key is wired (not load-bearing for tests)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all reused/stdlib, verified installed
- Architecture: HIGH — degradation contract + monotonic aggregation already in codebase; Phase 6 is wiring + one analyzer + one client
- Pitfalls: HIGH — inversion guard, budget, backoff, cache namespace all directly mapped to PITFALLS.md and verified codebase patterns
- PSI live behavior (host, keyless quota): MEDIUM — mocked in tests; confirm live before README

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable; PSI v5 API + stdlib are slow-moving)
