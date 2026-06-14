# Phase 2: Fetch + Existence (Dim 1) + Robustness - Research

**Researched:** 2026-06-14
**Domain:** Never-crashing HTTP fetch + URL normalization + Dimension-1 (Existenz & Substanz) verdict, offline-safe and offline-testable, slotted into the existing Phase-1 pipeline.
**Confidence:** HIGH (all behavior rests on documented `requests`/stdlib semantics and project decisions already locked in ARCHITECTURE.md; verified against installed lib versions and the actual sample data).

## Summary

Phase 2 turns the Phase-1 placeholder into a real Dimension-1 measurement. The job is narrow and well-bounded: take each row's URL cell, normalize it, probe a small set of scheme/www variants with a hard-timeout, header-rich, size-capped `requests.get` that **never raises**, and turn the outcome into an existence verdict — `dead` (no/unreachable/parked site) overrides Website-Bedarf to **5**; `social-only` and `thin` are strong-but-not-dead presence signals. SSL validity is captured now as a *fact* on the `FetchResult` (for Phase-3 Dimension-2 scoring) but does not block the fetch.

The critical constraint, stated three ways in the project docs, is **graceful degradation**: the tool AND its test suite must run with zero network. That means the fetch layer must be a thin seam that tests monkeypatch, and the existence analyzer must be a pure function over a `FetchResult` dataclass (no network inside it). Empty/broken URLs must score Bedarf 5 *without any network at all*, which the sample's two edge cases (`Kiosk am Lindenplatz` → empty URL; `Nähatelier Sutter` → `htp://naehatelier-sutter`) exercise directly.

This phase deliberately does NOT add the thread pool or the on-disk cache (those are Phase 5 per the locked roadmap) and does NOT do free-subdomain/`tldextract` analysis (Phase 3, Dimension 2). Keep `analyze_row` sequential; keep `zahl` on the existing placeholder; make only `bedarf` real where Dimension 1 dictates.

**Primary recommendation:** Add `lead_analyzer/fetch.py` (normalize + a single never-raising `fetch()` returning a `FetchResult`) and `lead_analyzer/analyzers/existence.py` (pure `analyze(fetch_result) -> DimensionVerdict`). Extend `models.py` with a `FetchResult` dataclass. Wire `analyze_row` to: empty URL → Bedarf 5 (no fetch); else `fetch()` → `existence.analyze()` → if `dead` Bedarf 5 else keep placeholder-ish Bedarf, always wrapped in a per-row `try/except Exception`. Test everything by monkeypatching `requests.Session.get` / injecting fake `FetchResult`s — no live network in code or tests.

## User Constraints (from project docs — no CONTEXT.md exists for this phase)

> No `*-CONTEXT.md` exists in the phase dir. Constraints below are extracted from CLAUDE.md (binding ACs), the locked roadmap decisions in STATE.md, and the phase brief. Treat these with the same authority as locked decisions.

### Locked Decisions (from STATE.md roadmap + ARCHITECTURE.md)
- **Smallest E2E slice first, then iterate** (CLAUDE.md §5). Phase 1 already ships Excel-in/Excel-out. Phase 2 adds *only* real fetch + Dim 1 + robustness — nothing else.
- **Cache + concurrency are Phase 5, not Phase 2.** Keep `analyze_row` sequential; do not add `ThreadPoolExecutor` or on-disk cache yet. (`config.workers`, `config.use_cache` exist but stay unused this phase.)
- **PageSpeed is Phase 6; LLM is v2.** Out of scope here.
- **Dimensions 2/4/5/6 are Phase 3.** Phase 2 measures Dimension 1 only — but *captures* the raw facts (ssl_ok, final_url, status, headers, html) that Phase 3 will read, per fetch-once-parse-many.
- **Architecture is decided** (ARCHITECTURE.md): `fetch.py` + `analyzers/existence.py`, `FetchResult` carrier, degradation contract, dead→5 override. Build on it; do not redesign.
- **No pandas** (table_io.py already enforces this; AC2 column fidelity).

### Claude's Discretion
- Exact variant-probe order and which `requests` exceptions map to which note string.
- Whether to use a `requests.Session` (recommended) vs bare `requests.get`.
- How SSL validity is captured (recommendation below: `verify=True` then catch `SSLError` and re-fetch `verify=False` to still read content — simplest robust path).
- Parked/social host lists and HTML markers (concrete lists provided below; tune freely).
- Test-seam mechanism (monkeypatch vs dependency injection — both fine; recommendation below).

### Deferred Ideas (OUT OF SCOPE this phase)
- On-disk per-URL cache, thread pool (Phase 5).
- Free/builder-subdomain detection, `tldextract`, SSL *scoring* (Phase 3 — but capture the SSL *fact* now).
- PageSpeed, robots.txt/sitemap, secondary-path fetches (`/impressum` etc.), LLM.
- Zahlungskräftigkeit logic (Phase 4) — `zahl` stays on the Phase-1 placeholder.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BED-01 | Dimension 1 *Existenz & Substanz* really measured: reachable (HTTP 200 after http/https + www-variant probe), parked/placeholder, social-only, thin content. | URL normalization order + variant-probe sequence (Pattern 1); existence verdict mapping with concrete host/marker lists (Pattern 3); dead→5 override (Pattern 4). |
| ROB-01 | Empty URL, broken URL (`htp://…`), unreachable, timeout, parked, social-only → never crash; each gets a sensible score (no website → Bedarf 5) + note. | Empty-URL short-circuit (no fetch); never-raising `fetch()` exception→note map (Pattern 2); both sample edge cases traced end-to-end. |
| ROB-02 | HTTP fetch has hard timeouts, browser-like UA, redirect/size limits, tolerant encoding fallback; SSL error becomes a Dim-2 signal not a crash. | The exact `requests` call shape (Pattern 2): `timeout=(connect,read)`, de-CH headers, `max_redirects`, `stream=True` byte cap, `errors="replace"` decode, SSL-as-signal capture (Pattern 5). |
| ROB-03 | One bad row/stage isolated by a per-row exception boundary; the run continues. | `analyze_row` bare-`except Exception` boundary returning a degraded `RowResult` (Pattern 6); sequential loop already in `pipeline.run`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL normalization | `fetch.normalize()` (pure) | — | String-only; no I/O; trivially unit-testable offline. |
| HTTP retrieval (variant probe, timeout, headers, size cap, SSL capture) | `fetch.fetch()` (I/O seam) | — | The ONLY place that touches the network. Tests monkeypatch here. Returns a `FetchResult`; never raises. |
| Existence verdict (reachable/parked/social/thin → dead/severe/gap/ok) | `analyzers/existence.py` (pure) | — | Pure function over `FetchResult`. No network → fully offline-testable with fixtures. |
| dead→Bedarf 5 override + keep `zahl` placeholder | `pipeline.analyze_row` + `scoring` | — | Orchestration glue; owns the per-row try/except boundary (AC4). |
| Carrier of raw fetch facts for later dims | `models.FetchResult` | — | fetch-once-parse-many: Phase 3 dims 2/4/5/6 read these same facts. |

**Key seam:** `fetch.fetch()` is the single network boundary. Everything above it (normalize) and below it (existence verdict, scoring) is pure and offline. This is what makes "tool and tests run with no network" achievable without elaborate HTTP mocking — you mock exactly one function.

## Standard Stack

### Core
| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| `requests` | 2.34.2 `[VERIFIED: .venv import]` | HTTP GET with timeout, redirects, headers, streamed body, SSL | Already a project dep; the de-facto Python HTTP client; exposes exactly the knobs ROB-02 needs. |
| `beautifulsoup4` (`bs4`) | 4.15.0 `[VERIFIED: .venv import]` | Parse title/body text for parked-marker and thin-content detection | Already a project dep; lenient parser tolerates the broken HTML SME sites serve. |
| stdlib `urllib.parse` | py 3.14.3 | Split/rebuild URL (scheme, host, www) during normalization | No dependency; deterministic; the correct tool for scheme/host surgery. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `ssl` | py 3.14.3 | Only if you choose the separate-socket SSL probe (NOT recommended — see Pattern 5) | Skip in Phase 2; `requests` `SSLError` capture is simpler and sufficient. |
| `pytest` | 9.1.0 `[VERIFIED: .venv import]` | Offline unit + integration tests with monkeypatch | All Phase-2 validation. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` with manual variant loop | `httpx` | httpx not installed; no benefit here; `requests` is already wired. Stick with `requests`. |
| Catch `SSLError` + refetch `verify=False` | Separate `ssl.wrap_socket` probe to read cert `notAfter` | The socket probe gives cert *expiry detail* but adds a second connection, more failure modes, and cert parsing — overkill for Phase 2 where we only need the boolean `ssl_ok`. Defer cert-detail to Phase 3 if ever needed. |
| Monkeypatch `requests` in tests | `responses` / `requests-mock` library | Not installed; adds a dep for something one-line monkeypatch of the `fetch()` seam already covers. Avoid. |

**Installation:** No new packages required for Phase 2. (`tldextract` will be needed in **Phase 3** for free-subdomain detection — it is NOT installed; flag for Phase 3, not now.)

**Version verification:**
```
requests 2.34.2 · bs4 4.15.0 · openpyxl 3.1.5 · pytest 9.1.0 · Python 3.14.3
```
`[VERIFIED: .venv/bin/python import on 2026-06-14]`

## Architecture Patterns

### System Architecture Diagram

```
analyze_row(record, url_col, config)            ← pipeline.py (sequential; per-row try/except)
   │
   │  raw = record.cells.get(url_col)
   ▼
fetch.normalize(raw) ──► None?  ──yes──►  RowResult(bedarf=5, "keine Website")   [NO NETWORK]
   │ candidate URLs                          (empty / not-URL-shaped)
   ▼
fetch.fetch(candidates, config)   ← THE ONLY NETWORK CALL (never raises)
   │  for each candidate variant:
   │     requests Session.get(timeout=(c,r), headers=de-CH+browser-UA,
   │                          allow_redirects=True, stream=True)  → cap bytes
   │     on SSLError → record ssl_ok=False, refetch verify=False to still read body
   │     on Timeout/ConnectionError/TooManyRedirects/* → try next variant
   │  first variant that yields a response wins
   ▼
FetchResult(url, ok, status, final_url, redirected, ssl_ok, headers, html, error)
   │
   ▼
existence.analyze(fetch_result) ── PURE ──►  DimensionVerdict(dim=1, level, reason)
   │   not ok / status≥400 / DNS-fail  → level="severe", reason "nicht erreichbar"  → DEAD
   │   parked markers / host           → level="severe", reason "geparkt"           → DEAD
   │   social host                     → level="severe", reason "Social-only"       → presence
   │   thin body text                  → level="gap",    reason "dünner Inhalt"
   │   reachable + substantial         → level="ok"
   ▼
scoring: dead → bedarf=5 (override, cannot be downgraded); else placeholder bedarf
zahl  = Phase-1 placeholder (unchanged this phase)
   ▼
RowResult(index, bedarf, zahl, reason, verdicts=[dim1])  → stable_sort → write
```

### Recommended Project Structure (additions only)
```
lead_analyzer/
├── fetch.py              # NEW: normalize(raw)->list[str]|None ; fetch(candidates,cfg)->FetchResult ; never raises
├── models.py             # EXTEND: add FetchResult dataclass
├── pipeline.py           # EDIT: real analyze_row with per-row try/except + dead→5
├── scoring.py            # EDIT (small): a bedarf-from-dim1 helper / dead override; keep clamp + stable_sort
└── analyzers/
    ├── __init__.py       # NEW (package marker)
    └── existence.py      # NEW: analyze(fetch_result)->DimensionVerdict (pure, offline)
tests/
├── test_fetch.py         # normalize() cases + fetch() with monkeypatched Session.get
├── test_existence.py     # analyze() over hand-built FetchResult fixtures
└── test_pipeline_dim1.py # analyze_row offline (empty/broken URL → Bedarf 5), no network
```

### Pattern 1: URL normalization + variant-probe order

**What:** A pure `normalize(raw) -> list[str] | None` that produces an *ordered* candidate list; `None` means "no URL at all → caller scores Bedarf 5 with no fetch."

**Normalization rules (apply in order):**
1. `None` / empty / whitespace-only → return `None`. `[VERIFIED: sample row 200041 'Kiosk' has cell=None]`
2. `str(raw).strip()`; lowercase the **scheme+host only** (never lowercase a path — paths can be case-sensitive). For Phase 2 we fetch the homepage, so path is usually empty anyway.
3. Fix the known scheme typo: a leading token matching `r'^h[t]+p?s?://'` that isn't a valid `http(s)://` → treat as schemeless. Concretely, `htp://naehatelier-sutter` → strip the bad `htp://`, leaving bare host `naehatelier-sutter`. `[VERIFIED: sample row 200042]`
   - General rule: if it starts with something `://`-ish that is not exactly `http://` or `https://`, drop everything up to and including `://` and treat the remainder as a bare host.
4. If no scheme now, treat the whole string as a bare host (+ optional path).
5. Reject obvious non-URLs: after stripping scheme, the host must contain at least one `.` OR be a known single-label that resolves — `naehatelier-sutter` has **no dot**, so it is not a resolvable public host. **Recommendation:** if the host has no dot, still emit candidates (let DNS fail naturally and map to "nicht erreichbar") rather than hard-rejecting — this keeps one code path and the note comes out as "nicht erreichbar" which is correct for Bedarf 5. (Either choice yields Bedarf 5; emitting-and-failing is simpler and needs no separate "ungültige URL" branch, though a distinct note is a nice-to-have.)

**Variant-probe sequence (for a host `h`, possibly already `www.`):**
```
1. https://h
2. https://www.h        (only if h doesn't already start with www.)
3. http://h
4. http://www.h         (only if h doesn't already start with www.)
```
- If the input already had a working-looking scheme+host, put that exact URL first, then the permutations as fallbacks.
- **Stop at the first variant that returns a `requests` Response** (any status, even 4xx/5xx — a response means the host exists; status interpretation is the analyzer's job). Do NOT keep probing variants after a real HTTP response.
- Only move to the next variant on a *connection-level* failure (DNS, refused, timeout, SSL handshake fail you couldn't recover, TooManyRedirects).
- Declare **"nicht erreichbar"** only after ALL variants fail at the connection level.

**When to declare dead vs retry a variant:**
- Got an HTTP response (even 403/500): stop probing. (403/406/429 = "blocked, not assessable" — see Pitfall: don't score a WAF block as Bedarf 5; see Pattern 3 verdict table.)
- Connection error on this variant: try next variant.
- All variants exhausted with connection errors: `error="nicht erreichbar"`, `ok=False` → dead.

```python
# fetch.py — Source: requests docs (timeouts/redirects/stream) + project ARCHITECTURE.md
from urllib.parse import urlsplit, urlunsplit

def normalize(raw) -> list[str] | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # strip a malformed scheme like 'htp://'
    if "://" in s:
        scheme, _, rest = s.partition("://")
        if scheme.lower() not in ("http", "https"):
            s = rest                      # 'htp://naehatelier-sutter' -> 'naehatelier-sutter'
    parts = urlsplit(s if "://" in s else "https://" + s)
    host = parts.netloc.lower()
    if not host:
        return None
    path = parts.path or ""
    bare = host[4:] if host.startswith("www.") else host
    has_www = host.startswith("www.")
    def mk(scheme, h): return urlunsplit((scheme, h, path, parts.query, ""))
    out = [mk("https", host)]
    if not has_www: out.append(mk("https", "www." + bare))
    out.append(mk("http", host))
    if not has_www: out.append(mk("http", "www." + bare))
    # dedupe preserving order
    seen, uniq = set(), []
    for u in out:
        if u not in seen: seen.add(u); uniq.append(u)
    return uniq
```

### Pattern 2: The never-crashing `fetch()` call shape (ROB-02 core)

**What:** One function that takes the candidate list and returns a `FetchResult`. It catches *everything* and translates to a note; it never raises. Use a `requests.Session` so headers/redirect-cap are set once.

**Exact knobs (all required by ROB-02):**
| Knob | Value | Why |
|------|-------|-----|
| `timeout` | `(config.timeout_connect, config.timeout_read)` = `(5.0, 10.0)` (fields already exist in `config.py`) | requests has **no default timeout** — the #1 footgun (Pitfall 2). Tuple separates connect vs read stalls. |
| Headers | `User-Agent` = a real browser string; `Accept-Language: de-CH,de;q=0.9,en;q=0.5`; `Accept: text/html,...` | Avoid 403 from Swiss WAFs/Cloudflare on `python-requests/x` UA (Pitfall 3). de-CH biases language for later German keyword dims. |
| `allow_redirects` | `True` | http→https and bare→www redirects are normal and a *positive* signal; capture `response.url` as `final_url`. |
| `session.max_redirects` | low cap, e.g. `10` (default 30) | Bound redirect loops; `TooManyRedirects` is caught, not crashed (Pitfall 6). |
| `stream=True` + byte cap | read at most ~2 MB via `resp.raw.read` / `iter_content`, then stop | All Dim-1 signals (title, body text) live in the first chunk; prevents `MemoryError`/endless-body stall (Pitfall 5). |
| Decode | prefer declared charset, fall back to `resp.apparent_encoding`, decode with `errors="replace"` | Swiss latin-1/win-1252 pages mustn't raise `UnicodeDecodeError`; mojibake degrades a signal, a crash violates AC4 (Pitfall 6). |
| `verify` | `True` first; on `SSLError` set `ssl_ok=False`, then refetch with `verify=False` to still read body (Pattern 5) | Capture SSL as a Dim-2 *signal*, never silently ignore, never crash (Pitfall 7). |

**Exception → note map (catch these, in this order of specificity):**
| Exception | `ok` | note (`error`) | Resulting Dim-1 |
|-----------|------|----------------|------------------|
| `requests.exceptions.SSLError` | (recover via verify=False; if that also fails) `False` | "SSL-Fehler" + `ssl_ok=False` | if body recovered: normal analysis with ssl_ok=False; if not: dead |
| `requests.exceptions.ConnectTimeout` / `ReadTimeout` / `Timeout` | `False` | "Timeout" | try next variant; if all fail → dead "nicht erreichbar (Timeout)" |
| `requests.exceptions.ConnectionError` (DNS, refused, reset) | `False` | "nicht erreichbar" | next variant; all fail → dead |
| `requests.exceptions.TooManyRedirects` | `False` | "Redirect-Schleife" | next variant; all fail → dead |
| `requests.exceptions.RequestException` (catch-all for requests) | `False` | "Abruf-Fehler" | next variant; all fail → dead |
| `Exception` (bare, last resort inside fetch) | `False` | f"Fetch-Ausnahme: {type.__name__}" | dead — guarantees fetch() itself never raises |

**Got a Response (any status):** `ok = (200 <= status < 400)` for "reachable" purposes, but **store the status either way**. A 4xx/5xx still means the host answered — the analyzer decides (e.g. 403 = "blockiert, nicht bewertbar"; 404/410/5xx = effectively no usable site → lean toward dead/severe). Set `final_url = resp.url`, `redirected = (final_url != requested)`, `headers = dict(resp.headers)`, `html = decoded body (capped)`.

```python
# fetch.py — Source: requests docs (Session, timeouts, stream, verify) + Pitfalls.md
import requests

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_MAX_BYTES = 2_000_000

def _read_capped(resp) -> str:
    chunks, total = [], 0
    for chunk in resp.iter_content(8192):
        chunks.append(chunk); total += len(chunk)
        if total >= _MAX_BYTES: break
    raw = b"".join(chunks)
    enc = resp.encoding or resp.apparent_encoding or "utf-8"
    return raw.decode(enc, errors="replace")

def fetch(candidates: list[str], config) -> "FetchResult":
    session = requests.Session()
    session.max_redirects = 10
    session.headers.update(_HEADERS)
    timeout = (config.timeout_connect, config.timeout_read)
    last_err = "nicht erreichbar"
    for url in candidates:
        for verify in (True, False):            # second pass only taken on SSLError
            try:
                resp = session.get(url, timeout=timeout, allow_redirects=True,
                                   stream=True, verify=verify)
                html = _read_capped(resp)
                return FetchResult(
                    url=url, ok=(200 <= resp.status_code < 400),
                    status=resp.status_code, final_url=resp.url,
                    redirected=(resp.url != url), ssl_ok=verify,  # False if we fell back
                    headers=dict(resp.headers), html=html, error=None)
            except requests.exceptions.SSLError:
                last_err = "SSL-Fehler"
                continue                         # retry same url with verify=False
            except requests.exceptions.Timeout:
                last_err = "Timeout"; break      # next candidate
            except requests.exceptions.TooManyRedirects:
                last_err = "Redirect-Schleife"; break
            except requests.exceptions.RequestException:
                last_err = "nicht erreichbar"; break
            except Exception as e:               # belt-and-braces: fetch never raises
                last_err = f"Fetch-Ausnahme: {type(e).__name__}"; break
    return FetchResult(url=candidates[0] if candidates else "", ok=False, status=None,
                       final_url=None, redirected=False, ssl_ok=False,
                       headers={}, html=None, error=last_err)
```
> Note the `verify` loop: `(True, False)` is only fully traversed when `True` raised `SSLError`; on any other exception we `break` to the next candidate. On a clean `True` fetch we `return` immediately and never touch `verify=False`.

### Pattern 3: Existence verdict (pure, offline) — BED-01

**What:** `analyze(fr: FetchResult) -> DimensionVerdict` with `dim=1`. No I/O. Priority order matters (first match wins):

| # | Condition (on `FetchResult` / `final_url` host / `html`) | level | reason | Override? |
|---|----------------------------------------------------------|-------|--------|-----------|
| 1 | `fr.error` set AND `fr.html is None` (all variants failed) | `severe` | "nicht erreichbar" (+ specific: Timeout/SSL/Redirect) | **DEAD → Bedarf 5** |
| 2 | `fr.status` in {403,406,429} | `gap` | "blockiert – nicht bewertbar" | NOT dead; neutral/conservative (do NOT make 5) |
| 3 | `fr.status` ≥ 400 (404/410/5xx) and no body | `severe` | "nicht erreichbar (HTTP {status})" | **DEAD → 5** |
| 4 | host of `final_url` in PARKED_HOSTS, or title/body matches PARKED_MARKERS | `severe` | "geparkt/Platzhalter" | **DEAD → 5** |
| 5 | host of `final_url` (or input) in SOCIAL_HOSTS | `severe` | "Social-only" | NOT dead (there *is* presence) — strong toward 5 |
| 6 | visible body text < ~300 words / < ~512 chars | `gap` | "dünner Inhalt" | not dead |
| 7 | reachable (200–399) with substantial content | `ok` | "erreichbar, Inhalt vorhanden" | — |

**PARKED_HOSTS** `[CITED: FEATURES.md Dim-1 table]`: `sedoparking.com`, `parkingcrew.net`, `bodis.com`, `above.com`, `dan.com`, `afternic.com`, `hugedomains.com`, `domainmarket.com`.

**PARKED_MARKERS** (case-insensitive substring in title or first ~1KB of visible text) `[CITED: FEATURES.md]`: `"diese domain"`, `"domain parken"`, `"domain is for sale"`, `"buy this domain"`, `"this domain is for sale"`, `"website coming soon"`, `"under construction"`, `"in arbeit"`, `"standardseite"`, default-server pages: `"apache2 ubuntu default page"`, `"welcome to nginx"`, `"iis windows server"`.

**SOCIAL_HOSTS** `[CITED: FEATURES.md]`: `facebook.com`, `m.facebook.com`, `fb.com`, `instagram.com`, `linktr.ee`, `linkedin.com`, `tiktok.com`, `t.me`, `xing.com`. (Check both the *input* host — sometimes the URL itself is a FB page — and the `final_url` host after redirects.)

**Visible-text extraction:** `BeautifulSoup(html, "html.parser")`, drop `script`/`style`/`nav`/`footer` tags, `get_text(" ", strip=True)`, split on whitespace for a word count. `html.parser` (stdlib, no lxml dep) is sufficient and lenient. `[ASSUMED: thin thresholds ~300 words / ~512 chars]` — these are heuristic cutoffs from FEATURES.md, not empirically tuned; safe to start there and adjust against the sample.

```python
# analyzers/existence.py — pure, offline.  Source: FEATURES.md Dim-1 + scoring doc edge-cases
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

def analyze(fr) -> "DimensionVerdict":
    if fr.error and not fr.html:
        return DimensionVerdict(1, "severe", f"nicht erreichbar ({fr.error})", "html")
    if fr.status in (403, 406, 429):
        return DimensionVerdict(1, "gap", "blockiert – nicht bewertbar", "html")
    if fr.status is not None and fr.status >= 400 and not fr.html:
        return DimensionVerdict(1, "severe", f"nicht erreichbar (HTTP {fr.status})", "html")
    host = urlsplit(fr.final_url or fr.url or "").netloc.lower().removeprefix("www.")
    text = ""
    title = ""
    if fr.html:
        soup = BeautifulSoup(fr.html, "html.parser")
        for t in soup(["script", "style", "nav", "footer"]): t.decompose()
        title = (soup.title.string or "").strip().lower() if soup.title else ""
        text = soup.get_text(" ", strip=True)
    low = (title + " " + text[:1024]).lower()
    if host in PARKED_HOSTS or any(m in low for m in PARKED_MARKERS):
        return DimensionVerdict(1, "severe", "geparkt/Platzhalter", "html")
    if host in SOCIAL_HOSTS:
        return DimensionVerdict(1, "severe", "Social-only", "html")
    if len(text.split()) < 300:
        return DimensionVerdict(1, "gap", "dünner Inhalt", "html")
    return DimensionVerdict(1, "ok", "erreichbar, Inhalt vorhanden", "html")
```

### Pattern 4: `analyze_row` integration — dead→5 override, keep `zahl` placeholder (ROB-03)

**What:** Wire the seam into the existing sequential `analyze_row`, wrapped in the AC4 boundary. Empty URL short-circuits with NO fetch. `zahl` stays on the Phase-1 placeholder (Phase 4 owns it). Only `bedarf` becomes real where Dim-1 dictates; non-dead reachable rows can keep a provisional bedarf (e.g. 3) until Phase-3 aggregation exists.

```python
# pipeline.py — Source: ARCHITECTURE.md Pattern 2/5 + Pitfalls.md #1
def analyze_row(record, url_col, config):
    try:
        raw = record.cells.get(url_col)
        candidates = fetch.normalize(raw)
        if candidates is None:                      # empty URL → NO network
            return RowResult(record.index, bedarf=5, zahl=_zahl_placeholder(),
                             reason="keine Website")
        fr = fetch.fetch(candidates, config)        # never raises
        v = existence.analyze(fr)                    # pure
        dead = v.level == "severe" and v.reason.startswith(
            ("nicht erreichbar", "geparkt"))          # dead causes
        if dead:
            bedarf = 5                               # final override, cannot downgrade
        else:
            bedarf = 4 if v.level == "severe" else (3 if v.level == "gap" else 3)
            # provisional until Phase-3 aggregation; social-only=severe→4 leans high
        return RowResult(record.index, bedarf=clamp_score(bedarf),
                         zahl=_zahl_placeholder(), reason=v.reason, verdicts=[v])
    except Exception as e:                            # AC4 per-row boundary — the run continues
        return RowResult(record.index, bedarf=5, zahl=_zahl_placeholder(),
                         reason=f"Fehler: {type(e).__name__}")
```
- **dead set** = `{nicht erreichbar*, geparkt*}`. Social-only and thin are NOT dead (presence exists) → they get a high-but-not-overridden bedarf and Phase 3 will refine.
- `_zahl_placeholder()` = whatever the current placeholder yields (constant 3 today). Do not implement real Zahlungskräftigkeit.
- The override `bedarf = 5` is set as a literal final value; nothing after it can lower it (Pitfall 9).

### Pattern 5: SSL captured as a Dim-2 *signal* in Phase 2 (recommended approach)

**Recommendation:** `verify=True` first; on `requests.exceptions.SSLError`, set `ssl_ok=False` and **refetch the same URL with `verify=False`** to still read the body for Dim-1 (and later dims). Store `ssl_ok` on `FetchResult`. Phase 3's Dimension-2 analyzer will *score* `ssl_ok`; Phase 2 only records the fact.

**Why not the separate `ssl.wrap_socket` probe:** it opens a second connection, needs cert parsing (`getpeercert()`, `notAfter` date math, hostname match), and has its own failure modes — all to produce the same boolean we already get for free from `requests`. `[ASSUMED]` cert-expiry *detail* (days-until-expiry) is not needed for the 1–5 score; defer it. Suppress `urllib3 InsecureRequestWarning` *after* capturing the signal (so logs stay clean) via `urllib3.disable_warnings(InsecureRequestWarning)` — only on the verify=False refetch path.

### Anti-Patterns to Avoid
- **Doing network I/O inside `existence.analyze`.** It must be pure over `FetchResult` so tests run offline. (Breaks the no-network test constraint.)
- **Catching only `requests.RequestException` at the row level.** The row boundary must be bare `except Exception` (Pitfall 1) — bs4/decode/`ValueError` etc. also occur.
- **`verify=False` globally.** Loses the SSL signal and masks failures (Pitfall 7). Capture the signal first, downgrade per-request only.
- **Scoring a 403/429 WAF block as Bedarf 5.** A good modern site behind Cloudflare must not become a top "needs-website" lead (Pitfall 3).
- **Probing more variants after a real HTTP response.** A 404/500 is an answer — stop; don't waste requests or mis-merge results from different variants.
- **Adding the thread pool or cache now.** That's Phase 5; keep `analyze_row` sequential (locked decision).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP with timeout/redirect/stream/SSL | A `urllib`/socket client | `requests.Session` | Handles connection pooling, redirects, decompression, SSL — already a dep. |
| Charset detection for Swiss latin-1/win-1252 pages | A charset sniffer | `resp.apparent_encoding` (charset_normalizer, ships with requests) + `errors="replace"` | requests already bundles detection; reinventing it adds bugs (Pitfall 6). |
| HTML title/text extraction from messy SME markup | regex over HTML | `BeautifulSoup(html, "html.parser")` | Lenient parser; regex-on-HTML is the classic trap; bs4 already a dep. |
| URL scheme/host surgery | string slicing | `urllib.parse.urlsplit`/`urlunsplit` | Correct handling of ports, userinfo, query; stdlib. |

**Key insight:** Phase 2's only genuinely custom logic is (a) the variant-probe ordering and (b) the existence verdict thresholds. Everything else (HTTP, decode, parse, URL split) is library work — keep the custom surface tiny and pure so it's testable offline.

## Common Pitfalls

### Pitfall 1: One bad row aborts the whole run
**What goes wrong:** A malformed URL / SSL / decode / parser error escapes `analyze_row`; the 300-row run dies and prior work is lost.
**Why:** Wrapping only the happy path or catching only `requests` exceptions.
**How to avoid:** Bare `except Exception` boundary in `analyze_row` returning a degraded `RowResult` (Pattern 4). Narrower handlers inside `fetch()` produce the specific note.
**Warning signs:** Any `except requests.X` with no outer catch-all; tests that only feed clean URLs.

### Pitfall 2: No timeout → run hangs forever
**What goes wrong:** `requests.get` with no `timeout` blocks on a dead Swiss host indefinitely.
**Why:** requests has no default timeout.
**How to avoid:** Always `timeout=(connect, read)` (fields already in `config.py`). Treat `Timeout` as a normal outcome → note "Timeout", next variant.
**Warning signs:** Any `get()` without `timeout=`; "sometimes takes 20 minutes."

### Pitfall 3: Default UA gets 403'd → good site mis-scored as dead
**What goes wrong:** WAF blocks `python-requests/x` → 403 → tool calls it Bedarf 5.
**How to avoid:** Browser UA + de-CH headers; map 403/406/429 to "blockiert – nicht bewertbar" with a neutral score, NOT 5 (Pattern 3 row 2).
**Warning signs:** Many "nicht erreichbar" 5s for sites that load in a browser.

### Pitfall 4: http/https/www permutations → false "not reachable"
**How to avoid:** Variant-probe order (Pattern 1); record which variant worked; declare dead only after all fail at connection level.

### Pitfall 5: SSL crash vs. SSL ignored
**How to avoid:** Capture `ssl_ok=False`, refetch `verify=False` to read body (Pattern 5). Never global `verify=False`.

### Pitfall 6: Huge/streaming bodies + non-UTF8 encodings
**How to avoid:** `stream=True` + 2 MB cap; decode with declared→apparent encoding and `errors="replace"`.

## Code Examples

(See Patterns 1–5 above — each carries a runnable, source-tagged snippet for `normalize`, `fetch`, `existence.analyze`, and `analyze_row`.)

### FetchResult dataclass (add to models.py)
```python
# models.py — Source: ARCHITECTURE.md Data Flow carrier list
@dataclass
class FetchResult:
    url: str                       # the variant actually requested
    ok: bool                       # True iff a 200–399 response was obtained
    status: int | None             # HTTP status, or None if no response
    final_url: str | None          # response.url after redirects
    redirected: bool
    ssl_ok: bool                   # True if verify=True succeeded; False if we fell back / no TLS
    headers: dict                  # response headers (for Phase 3 dims)
    html: str | None               # decoded, size-capped body; None if unreachable
    error: str | None              # note string on failure; None on success
```

## Runtime State Inventory

> Greenfield code addition (new modules + extend existing), no rename/migration. Section included for completeness; categories verified.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 2 adds no datastore (cache is Phase 5). | none |
| Live service config | None — no external service registration. | none |
| OS-registered state | None. | none |
| Secrets/env vars | None — no API keys this phase (PageSpeed is Phase 6; `.env` not read yet). | none |
| Build artifacts | `lead_analyzer/analyzers/` is a NEW package — needs `__init__.py` so imports resolve. No stale artifacts. | create `analyzers/__init__.py` |

## Validation Architecture

> `nyquist_validation` config key not found (no `.planning/config.json` present at research time) → treated as ENABLED. This section drives VALIDATION.md.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.0 `[VERIFIED]` |
| Config file | none detected — add `tests/` dir; pytest auto-discovers `test_*.py`. (Optional: a `pytest.ini`/`pyproject [tool.pytest]` — Wave 0 nicety, not required.) |
| Quick run command | `.venv/bin/python -m pytest tests/test_fetch.py tests/test_existence.py -x -q` |
| Full suite command | `.venv/bin/python -m pytest -q` |

**Offline guarantee:** No test may touch the network. The `fetch()` seam is the only network point; tests monkeypatch `requests.Session.get` (or inject fake `FetchResult`s into `existence.analyze`/`analyze_row`). Recommend a `conftest.py` autouse fixture that monkeypatches `requests.Session.get` to raise `AssertionError("network used in tests")` by default, so any accidental real request fails loudly.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BED-01 | `normalize()` produces correct variant order for bare host, `www.`, full URL, `htp://` typo, `None`→None | unit | `pytest tests/test_fetch.py::test_normalize -q` | ❌ Wave 0 |
| BED-01 | `existence.analyze()`: reachable→ok, parked-host→severe, social-host→severe, thin→gap, 403→gap "blockiert" | unit | `pytest tests/test_existence.py -q` | ❌ Wave 0 |
| ROB-01 | empty-URL row → Bedarf 5 "keine Website", **no network** | unit | `pytest tests/test_pipeline_dim1.py::test_empty_url -q` | ❌ Wave 0 |
| ROB-01 | broken `htp://naehatelier-sutter` (DNS fail mocked) → Bedarf 5 "nicht erreichbar" | unit | `pytest tests/test_pipeline_dim1.py::test_broken_url -q` | ❌ Wave 0 |
| ROB-01 | timeout (mock raises `Timeout`) → Bedarf 5, note "Timeout", no crash | unit | `pytest tests/test_fetch.py::test_timeout -q` | ❌ Wave 0 |
| ROB-02 | `fetch()` sets `timeout`, browser UA, de-CH, `max_redirects`, byte cap (assert via captured kwargs on mocked `get`) | unit | `pytest tests/test_fetch.py::test_request_shape -q` | ❌ Wave 0 |
| ROB-02 | `SSLError` → `ssl_ok=False`, body still read via verify=False refetch, no crash | unit | `pytest tests/test_fetch.py::test_ssl_signal -q` | ❌ Wave 0 |
| ROB-02 | latin-1/win-1252 body decodes without raising (`errors="replace"`) | unit | `pytest tests/test_fetch.py::test_encoding_fallback -q` | ❌ Wave 0 |
| ROB-03 | analyzer raising mid-row → `analyze_row` returns degraded RowResult, loop continues | unit | `pytest tests/test_pipeline_dim1.py::test_row_boundary -q` | ❌ Wave 0 |
| ROB-01/03 | **Offline integration:** run pipeline over the real `data/sample_input.xlsx` with `fetch()` monkeypatched to a deterministic fake; assert `len(out)==len(in)`, all bedarf∈[1,5] int, Kiosk & Nähatelier rows = 5 | integration (offline) | `pytest tests/test_pipeline_dim1.py::test_sample_offline -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_fetch.py tests/test_existence.py -x -q`
- **Per wave merge:** `.venv/bin/python -m pytest -q` (includes Phase-1's 15 tests + new Phase-2 tests)
- **Phase gate:** Full suite green + the offline sample-integration test asserting both edge-case rows score 5, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/conftest.py` — autouse fixture blocking real network (monkeypatch `requests.Session.get` to fail); shared fake-`FetchResult` factory + fake-`Response` helper.
- [ ] `tests/test_fetch.py` — covers BED-01 (normalize) + ROB-02 (request shape, SSL, encoding, timeout).
- [ ] `tests/test_existence.py` — covers BED-01 verdict matrix.
- [ ] `tests/test_pipeline_dim1.py` — covers ROB-01/ROB-03 + offline sample integration.
- [ ] `lead_analyzer/analyzers/__init__.py` — package marker (import resolution).
- Framework install: none — pytest 9.1.0 already in `.venv`.

## Security Domain

> `security_enforcement` config not found (no config.json) → treated as enabled. Phase 2 makes outbound HTTP to untrusted third-party sites and parses their HTML; the relevant controls are about *defensive consumption*, not auth.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth in this phase. |
| V3 Session Management | no | No user sessions. |
| V4 Access Control | no | Local CLI. |
| V5 Input Validation | yes | URL normalization validates/sanitizes the untrusted cell value before fetch; size cap + timeout bound untrusted-server influence; decode `errors="replace"` prevents malformed-byte crashes. |
| V6 Cryptography | partial | TLS verification ON by default; `verify=False` used ONLY as a scoped fallback to read body after the invalid-cert signal is recorded — never globally. Suppress only the resulting InsecureRequestWarning, scoped. |

### Known Threat Patterns for {Python requests fetching untrusted SME sites}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Decompression/huge-body DoS (malicious endless or multi-GB response) | Denial of Service | `stream=True` + 2 MB byte cap; hard `timeout=(5,10)`. |
| Redirect loop / redirect to internal host (SSRF-ish) | DoS / Tampering | `max_redirects=10`; this is a batch lead tool with no internal network, but capping bounds abuse. `[ASSUMED]` SSRF risk is low (no internal services), but the redirect cap is the right guard regardless. |
| Malformed bytes / decompression-bomb HTML crashing the parser | DoS | size cap before `BeautifulSoup`; `html.parser` is pure-Python and bounded by the capped input. |
| Leaking scraped third-party data into git | Information Disclosure | Out of phase scope but noted: `.gitignore` `output/` (handled Phase 7); Phase 2 writes no persistent scraped data. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Thin-content thresholds (~300 words / ~512–1024 chars) are reasonable starting cutoffs | Pattern 3 | Low — only affects ok-vs-gap on borderline sites, not the dead→5 override or the two edge cases; tune against sample. |
| A2 | `naehatelier-sutter` (no dot) will fail DNS and map to "nicht erreichbar"→Bedarf 5 rather than needing a separate "invalid URL" branch | Pattern 1 | Low — both paths yield Bedarf 5; only the note string differs. Validated by the offline test that mocks the failure. |
| A3 | Cert-expiry *detail* (days remaining) is not needed for Phase 2/3 scoring; boolean `ssl_ok` suffices | Pattern 5 | Low/Medium — if Phase 3 later wants "expired vs untrusted" granularity, a socket probe can be added then; the boolean covers the 1–5 band. |
| A4 | `verify=False` refetch reliably succeeds when only the cert is invalid (handshake otherwise fine) | Pattern 5 | Low — if the refetch also fails, the row falls through to dead "SSL-Fehler"→5, which is still a sensible outcome. |
| A5 | 2 MB byte cap captures all Dim-1 (and later head/meta) signals | Pattern 2 | Low — title/body text and `<head>` metadata are front-loaded; very few sites push content past 2 MB before the readable body. |

**Empty?** No — five low-risk heuristic assumptions, none affecting the binding edge cases (empty/broken URL → 5) which are deterministic and tested offline.

## Open Questions

1. **Provisional non-dead Bedarf value (3 vs 4) before Phase-3 aggregation exists**
   - What we know: dead→5 is locked; social-only/thin are "high but not 5."
   - What's unclear: exact provisional integer for reachable-but-imperfect rows until Phase 3's 6-dimension aggregation lands.
   - Recommendation: keep reachable-ok at provisional `3` and severe-not-dead (social-only) at `4`; document it as provisional. Phase 3 replaces this with real aggregation. Does not affect AC compliance for Phase 2 (only Dim-1 + robustness are gated here).

2. **`tldextract` for free-subdomain detection**
   - What we know: NOT installed; needed for Dimension 2 (Phase 3), not Phase 2.
   - Recommendation: do NOT add it this phase; flag it as a Phase-3 install (`pip install tldextract`). Phase 2 only needs `urllib.parse` for host extraction.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.14.3 | — |
| requests | fetch.py | ✓ | 2.34.2 | — |
| beautifulsoup4 | existence.py text/title | ✓ | 4.15.0 | stdlib `html.parser` is the parser used (no lxml needed) |
| pytest | all tests | ✓ | 9.1.0 | — |
| Network access (live sites) | real runs only | best-effort | — | **Offline path is first-class:** empty/broken URL→5 with no network; tests fully mocked. |
| tldextract | Phase 3 (NOT this phase) | ✗ | — | n/a this phase — defer install to Phase 3 |

**Missing dependencies with no fallback:** None for Phase 2.
**Missing dependencies with fallback:** `tldextract` is absent but only needed in Phase 3; no impact now.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests.get(url)` no timeout | always `timeout=(connect,read)` | long-standing best practice | Mandatory here (ROB-02). |
| `verify=False` to "make SSL work" | verify ON, capture invalid-cert as a signal, scoped fallback | — | Turns a footgun into a Dim-2 data point. |

**Deprecated/outdated:** none relevant to this narrow phase.

## Sources

### Primary (HIGH confidence)
- Python `requests` documentation — timeouts (no default), `Session.max_redirects`, `stream`/`iter_content`, `verify`/`SSLError`, `apparent_encoding`, redirect handling. (HIGH)
- stdlib `urllib.parse`, `ssl`, `concurrent.futures` documentation. (HIGH)
- `.venv` import probe 2026-06-14: requests 2.34.2, bs4 4.15.0, openpyxl 3.1.5, pytest 9.1.0, Python 3.14.3. `[VERIFIED]`
- Sample-data probe: header `Website` is the URL column; row 200041 (Kiosk) cell=`None`; row 200042 (Nähatelier Sutter) = `htp://naehatelier-sutter`. `[VERIFIED]`
- Existing code read: `models.py`, `pipeline.py`, `scoring.py`, `config.py`, `table_io.py`. `[VERIFIED]`

### Secondary (project authoritative)
- `CLAUDE.md` (AC1, AC4, AC11), `docs/scoring_website_bedarf.md` (Dim-1 edge cases), `.planning/REQUIREMENTS.md` (BED-01, ROB-01/02/03), `.planning/STATE.md` (locked roadmap), `.planning/research/ARCHITECTURE.md` / `FEATURES.md` / `PITFALLS.md`.

### Tertiary (LOW confidence)
- Parked/social host lists and thin-content thresholds originate from FEATURES.md (training-knowledge sourced); tune against the sample. Marked `[ASSUMED]` where heuristic.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all installed versions verified.
- Architecture: HIGH — fully constrained by ARCHITECTURE.md (already decided); this phase implements a documented seam.
- Fetch call shape / robustness: HIGH — documented `requests` semantics + PITFALLS.md.
- Existence thresholds/host lists: MEDIUM — heuristic, tune against sample (does not affect the deterministic edge-case→5 behavior).

**Research date:** 2026-06-14
**Valid until:** ~2026-07-14 (stable libs; project-internal decisions). Re-check only if dependency versions change.
