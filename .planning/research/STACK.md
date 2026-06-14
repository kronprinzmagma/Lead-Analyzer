# Technology Stack

**Project:** Lead-Analyzer
**Researched:** 2026-06-14
**Overall confidence:** HIGH (core stack), MEDIUM (PageSpeed keyless limits, Zefix auth nuance)

## Guiding Principle

The stack is chosen for **graceful degradation** (CLAUDE.md Constraints + AC4): the tool must produce a score for every row even with **no API keys** and **no network** (pure heuristic fallback), and get progressively better when network → PageSpeed key → LLM key are available. Concretely this means:

- **Core (always works, offline-capable per row):** stdlib + `openpyxl` + `requests` + `beautifulsoup4`. Delivers Dimensions 1, 2, 4, 5, 6 + heuristic Zahlungskräftigkeit.
- **Tier 2 (network, keyless or keyed):** PageSpeed Insights API → Dimension 3; Zefix public REST → better Zahlungskräftigkeit.
- **Tier 3 (LLM key present):** Anthropic/OpenAI → qualitative Dimension 6 + payment-power refinement.

Each tier is gated by a capability check (key present? network reachable?) and **never** a hard dependency. A missing tier downgrades the score source and is recorded in the Begründung/log (AC5, AC6).

## Recommended Stack

### Core Framework (already installed — no new install needed)

| Technology | Version (installed) | Purpose | Why |
|------------|--------------------|---------|-----|
| Python | 3.14.3 | Runtime | venv already provisioned; modern stdlib (`concurrent.futures`, `ssl`, `urllib`, `json`, `argparse`, `dataclasses`) covers a lot |
| openpyxl | 3.1.5 | Read/write `.xlsx` | Already installed; reads + writes xlsx natively, preserves cell values, no pandas/NumPy weight. See Excel note below |
| requests | 2.34.2 | HTTP fetching of customer websites + JSON APIs | Already installed; battle-tested, simple `Session` + `Retry` adapter, sane timeout/redirect/SSL handling |
| beautifulsoup4 | 4.15.0 | HTML parsing (Dim. 1, 2, 4, 5, 6 signals) | Already installed; tolerant of broken HTML (essential — target sites are low-quality by definition) |

### Standard Library (no install — use aggressively before reaching for deps)

| Module | Purpose | Why over a 3rd-party lib |
|--------|---------|--------------------------|
| `concurrent.futures.ThreadPoolExecutor` | Concurrency for hundreds of rows | I/O-bound work (HTTP waits) → threads are ideal; no asyncio rewrite of `requests` needed. `max_workers=8–16` is plenty |
| `ssl` + `socket` | SSL-cert inspection (Dim. 2: valid cert? self-signed? expired?) | `ssl.create_default_connection`/`getpeercert()` gives issuer + `notAfter` without any dependency. `requests` alone tells you *if* TLS succeeded; stdlib `ssl` tells you *why* it failed and cert details |
| `urllib.parse` | URL normalization, domain extraction, free-subdomain detection (wixsite/jimdosite/…) | No dependency needed for Dim. 2 free-host detection |
| `json` | Cache files, JSON-LD parsing (Dim. 5), API response parsing | stdlib |
| `csv` | CSV input/output (spec allows CSV in + CSV out) | stdlib; pair with `openpyxl` for xlsx |
| `argparse` | Single CLI entry point (AC9: file in → file out) | stdlib |
| `logging` | Run log driving AC6 (which signals drove each score) | stdlib; write a per-row structured log line |
| `dataclasses` | Typed score result objects (per-dimension sub-verdicts → aggregate) | stdlib; keeps aggregation transparent (AC11) |

### Supporting Libraries (recommended new installs — small, justified)

| Library | Version | Purpose | When to Use | Justification for the dependency |
|---------|---------|---------|-------------|----------------------------------|
| **python-dotenv** | 1.2.2 | Load `.env` (API keys) | Always | AC9 requires `.env`-based keys; 1 tiny pure-Python dep, zero transitive deps. Alternative: read `os.environ` + a 10-line manual `.env` parser (viable if you want **zero** new deps — see Alternatives) |
| **lxml** | 6.1.1 | BeautifulSoup parser backend | Recommended | Faster + more robust than `html.parser` on malformed real-world HTML; bs4 uses it via `BeautifulSoup(html, "lxml")`. Ships manylinux/macos wheels → installs in seconds, no system libxml2 build. See parser note |

### Optional Libraries (install ONLY if you commit to the LLM tier)

| Library | Version | Purpose | Gate |
|---------|---------|---------|------|
| anthropic | 0.109.1 | Claude API (Dim. 6 qualitative + payment-power refinement) | Only call if `ANTHROPIC_API_KEY` in `.env`. Import lazily inside the gated branch so the package being absent never breaks the core run |
| openai | latest | OpenAI fallback | Only if `OPENAI_API_KEY` present and Anthropic absent |

**Do not add these to the mandatory requirements.** Lazy-import them; if the import fails, log "LLM layer unavailable" and continue. Alternatively skip the SDKs entirely and call the HTTP endpoints with `requests` (one fewer dep, full control over timeout/retry) — recommended for this project since you already have `requests` and only need a single messages call.

## Detailed Findings by Sub-Question

### 1. Excel/CSV read+write — use openpyxl, not pandas — confidence HIGH

- **openpyxl** is already installed and is the right tool: it reads `.xlsx` row-by-row preserving cell values, and writes `.xlsx` directly. No pandas/NumPy (tens of MB, slower install, would blow the <5-min setup margin for no benefit at this scale of a few hundred rows).
- **Preserving all original columns + types:** read the header row, keep every column in order, append the two score columns (+ optional Begründung) at the end. Write values back cell-by-cell. This guarantees AC2 "alle Original-Spalten unverändert."
  - Caveat: openpyxl reads **values**, not formulas-as-computed unless you `load_workbook(data_only=True)` (then it returns the last-cached computed value). For a customer list (plain values, no formulas) this is a non-issue; use the default and pass values straight through.
  - Mixed-type columns (numbers, strings, dates) round-trip fine because you copy the raw cell value object.
- **CSV:** use stdlib `csv` with `utf-8-sig` encoding (handles Excel's BOM) and `csv.Sniffer` or a `;` default (Swiss/European Excel exports often use `;`). Detect delimiter, don't hard-code.
- **Sorting (Section 3 spec):** sort rows in memory by `(Website-Bedarf desc, Zahlungskräftigkeit desc)` **before** writing, while keeping the full original row tuple intact so no original data is lost.
- **Why not pandas:** correct for big tabular analytics, overkill here, heavier install, and its type coercion (e.g., NaN, automatic dtype inference, date parsing) can *silently mutate* original columns — directly at odds with AC2 "unverändert." openpyxl's manual pass-through is safer for the "preserve everything" requirement.

### 2. Robust HTTP fetching — requests + urllib3 Retry + ThreadPoolExecutor — confidence HIGH

- **requests over httpx:** both are fine; `requests` is already installed, synchronous, and pairs cleanly with `ThreadPoolExecutor`. `httpx` only wins if you go full async — unnecessary for I/O-bound threading at this volume and would add a dep.
- **Retry/backoff: use `urllib3.util.retry.Retry` mounted on a `requests` Session adapter** — no extra dependency (urllib3 2.7.0 ships with requests). Configure:
  ```
  Retry(total=2, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        respect_retry_after_header=True)
  ```
  This satisfies AC8 (retry/backoff) for the website fetch. **For the PageSpeed/Zefix JSON APIs**, `Retry` with `respect_retry_after_header=True` handles 429 `Retry-After` automatically.
  - `tenacity` is a nicer decorator API but is an **extra dependency**; reserve it only if you want fancy retry policies around the LLM/API calls. Recommendation: skip tenacity, use urllib3 `Retry` for the adapter and a small manual backoff loop for API calls. Keeps deps at zero-new for HTTP.
- **Concurrency:** `ThreadPoolExecutor(max_workers=8–16)`. Website fetches are independent and I/O-bound. Cap workers to be polite and avoid local resource exhaustion. For the keyless PageSpeed API, run those calls on a **separate, smaller pool / rate-limited queue** (see §4) — don't blast 16 concurrent PSI calls.
- **Timeouts (critical for AC4 — must not hang on dead sites):** always pass `timeout=(connect, read)`, e.g. `timeout=(5, 10)`. Never call `requests.get` without a timeout (default is infinite → hang on parked/slow sites).
- **User-Agent:** set a real descriptive UA (e.g. `Lead-Analyzer/1.0 (+contact)`). Some sites block the default `python-requests/x` UA with 403 — which would wrongly look like "unreachable."
- **Redirect handling:** `requests` follows redirects by default. Inspect `resp.history` and `resp.url` for Dim. 1 (redirect to a social-media domain → "Social-only"; redirect to a parking page → "geparkt"). Also normalize `http://` ↔ `https://` and `www.` before declaring "unreachable" (the spec's broken-URL edge case `htp://…` needs scheme repair first).
- **SSL-cert inspection (Dim. 2):** two layers — (a) does `requests` complete over HTTPS without `SSLError`? (b) for cert details (issuer, expiry, self-signed), open a raw `ssl` socket with `getpeercert()`. To still *fetch* content from sites with broken certs (so you can score them), you may retry with `verify=False` and **record** "invalid SSL" as a Dim. 2 defect — the cert failure is itself signal, not just an error.
- **Parked-domain / placeholder detection:** heuristic on final HTML — tiny body, known parking strings ("domain for sale", "this domain is parked", default web-host landing markup), or a redirect to a registrar. Drives Dim. 1.

### 3. HTML parsing — BeautifulSoup with the lxml parser — confidence HIGH

- Use `BeautifulSoup(html, "lxml")`. Install `lxml` (6.1.1): faster and far more tolerant of the malformed markup typical of the low-quality target sites than the stdlib `html.parser`. If you want **zero new deps**, `html.parser` works and is acceptable — but lxml is worth the one wheel install for robustness on garbage HTML.
- Signal extraction map:
  - **Dim. 4 SEO:** `<title>` presence + length, `<meta name="description">` presence + length, `<link rel="canonical">`, `<meta name="robots">` (noindex?), `<h1>` count, `<html lang>`.
  - **Dim. 3 (HTML-side of mobile):** `<meta name="viewport">` presence/content (responsive proxy without PageSpeed).
  - **Dim. 5 KI-readiness:** `<script type="application/ld+json">` blocks → parse with `json` to confirm valid Schema.org; Open Graph `<meta property="og:*">` tags.
  - **Dim. 6 content/conversion:** `<form>` with input fields, `a[href^="tel:"]`, `a[href^="mailto:"]`, presence of an "Impressum"/"Kontakt" link, copyright year regex in footer text (aktualitäts-proxy), `<meta name="generator">` (outdated builder detection — also feeds Dim. 2 free-host signal).
- **robots.txt / sitemap.xml (Dim. 4):** separate cheap `GET /robots.txt` and `GET /sitemap.xml` HEAD/GET checks; don't try to parse from the page HTML.

### 4. Google PageSpeed Insights API v5 (Dimension 3) — confidence HIGH on endpoint, MEDIUM on keyless limits

- **Endpoint (GET):**
  `https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed`
- **Key parameters:**
  - `url` (required) — the customer site URL.
  - `strategy=MOBILE` (the spec specifically wants mobile — Dim. 3 "Mobile & Performance").
  - `category=PERFORMANCE` and `category=SEO` (repeat the param to request multiple categories; SEO category gives you a Lighthouse-audited SEO score that complements your own HTML SEO parse for Dim. 4).
  - `key=<PAGESPEED_API_KEY>` — **omit entirely when no key** → the API still answers (keyless works), just with stricter, sharable rate limits.
  - optional `locale=de`.
- **Keyless vs keyed:** Keyless requests succeed but share a low, undocumented anonymous quota and will 429 under concurrency. With a free key you get the documented quota of **25,000 requests/day and ~400 requests/100s** per Cloud project (HIGH confidence — Google docs). The free key is the right default for "a few hundred rows."
- **Rate-limit handling (AC8):** PSI returns HTTP **429** with a `Retry-After` header when throttled. Honor it. Because PSI calls are slow (~3–10s each, real Lighthouse run) and rate-limited, treat them as a **separate, serialized-or-low-concurrency stage** with a small worker count (2–4) and exponential backoff on 429/5xx. Cache every result to disk (AC7) so a re-run never re-hits PSI for already-scored URLs.
- **Graceful degradation:** if no network OR PSI 429s persist OR no key and keyless is exhausted → fall back to the **viewport-meta heuristic** (§3) for Dim. 3 and record "PageSpeed unavailable — viewport heuristic used" in the Begründung. This keeps Dim. 3 "at least heuristic" per AC11.
- **What to read from the response:** `lighthouseResult.categories.performance.score` (0–1), `...categories.seo.score`, and optionally Core Web Vitals from `loadingExperience`/`lighthouseResult.audits` (LCP, CLS). Map score bands → Dim. 3 sub-verdict (ok / Lücke / schwere Lücke).

### 5. Swiss company data — Zefix PublicREST API — confidence MEDIUM (auth nuance)

- **Endpoint base:** `https://www.zefix.admin.ch/ZefixPublicREST/api/v1`
- **Most useful call:** `POST /api/v1/company/search` with a JSON body containing a `name` (and optional canton/legalForm) → returns matching legal entities with **legal form** (AG/GmbH/Einzelfirma), status (active/deleted), seat/canton, UID. Legal form + (where present) capital/branch count is exactly the Zahlungskräftigkeit signal (AC5).
- **Detail calls:** `GET /api/v1/company/uid/{uid}`, `/chid/{chid}`, `/ehraid/{ehraid}`.
- **Auth — important nuance:** The Zefix PublicREST is published as **Open Government Data (OGD, open-use license)** and the search endpoint is documented in public Swagger at `https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html`. The `validitylabs/zefix` wrapper README references `USR`/`PWD`, which suggests some access paths expect basic auth. **This is unresolved from docs alone.** Recommendation:
  1. Treat Zefix as **best-effort, optional** (like PageSpeed). Attempt the keyless/anonymous `POST .../company/search`; if it returns 401/403, log "Zefix requires credentials — skipped" and fall back to the heuristic.
  2. Make any credentials optional via `.env` (`ZEFIX_USER`, `ZEFIX_PASSWORD`) and only send them if present.
  3. **Verify the actual auth requirement at build time** with a single live probe against the search endpoint (one curl) before wiring it in — do not assume from training data.
- **Rate limits:** not officially documented. Be conservative: serialize Zefix calls, cache by company name/UID, add a small delay. Zefix data is static per company → cache aggressively (AC7).
- **Primary fallback (and arguably the default for v1):** derive Zahlungskräftigkeit **heuristically without Zefix** from (a) **legal form parsed from the company name** ("… AG" → higher capital floor → higher score; "GmbH" → mid; no suffix / "Einzelfirma" → lower), (b) **branch/industry** from the existing "Branche" column (Zahnarzt/Treuhand/Immobilien rank higher than Coiffeur/Kiosk), and (c) **website substance signals** (multiple locations, team page, professional domain). This satisfies AC5 ("nachvollziehbare Schätzung, keine erfundenen Fakten") with zero external dependency, and Zefix becomes a confidence-booster when reachable.
- **Alternative sources:** opendata.swiss publishes a downloadable Zefix dataset (LINDAS/Linked Data) — heavier, but usable fully offline if you want a local lookup table. Overkill for v1; note as a future option.

### 6. Optional LLM layer — gated, structured output — confidence HIGH

- **Gate:** run only if `ANTHROPIC_API_KEY` (preferred) or `OPENAI_API_KEY` is present in `.env`. Lazy-import the SDK inside the branch (or skip the SDK and POST to the REST endpoint with `requests`). If absent → skip, the deterministic Dim. 6 checks stand alone (spec: LLM is *Ergänzung, nicht Ersatz*).
- **Model choice:** `claude-haiku-4-5` is the right default — cheap, fast, good enough for "summarize this page text, rate content freshness/professionalism 1–5 with a one-line reason." Reserve `claude-sonnet` (e.g. sonnet-4.x) for harder payment-power reasoning if needed. (Verify exact current model IDs at build time via the Anthropic models list — IDs evolve.)
- **Structured output:** request **strict JSON**. With Anthropic, either use **tool-use / `tools` with an input schema** (most reliable structured output) or instruct "respond with only this JSON shape" and parse defensively. With OpenAI, use `response_format={"type":"json_object"}` / structured outputs. Always wrap parsing in try/except → on malformed output, discard the LLM contribution and keep deterministic scores (robustness > LLM).
- **Cost/limits (AC8):** batch sparingly, cache LLM verdicts per URL on disk, cap input (send extracted text/title/meta, not full HTML), set a per-call timeout, and retry once on rate-limit. The LLM should touch only the qualitative slice of Dim. 6 and optionally nudge Zahlungskräftigkeit — never the deterministic dimensions.

### 7. Config & caching — python-dotenv + a JSON-file disk cache — confidence HIGH

- **Secrets:** `python-dotenv` 1.2.2 to load `.env` → `os.environ`. `.env` already in scope-protection (.gitignore, never commit). Capability flags derive from presence of keys. (Zero-dep alternative: a ~10-line `.env` parser if you refuse the dependency — but dotenv is trivial and standard.)
- **Caching (AC7 resümierbar + AC8 avoid duplicate API calls):** Recommendation: a **per-URL JSON cache** — one cache directory, key = hash(url), value = `{fetched_at, http_result, parsed_signals, pagespeed, zefix, llm}`. Rationale:
  - **Transparent & inspectable** (matches CLAUDE.md "Transparenz vor Eleganz") — you can open a cache file and see exactly what was cached.
  - **Crash-safe / resumable:** each row's cache is written as soon as it's computed, so an abort mid-run loses only the in-flight row. Re-running skips cached rows.
  - **Zero dependency** (stdlib `json` + `pathlib` + `hashlib`).
  - Avoids re-hitting PageSpeed/Zefix/LLM on re-run → directly serves AC8.
- **Why not shelve/diskcache:** `shelve` uses pickle (opaque, not human-inspectable, version-fragile). `diskcache` is excellent (SQLite-backed, thread-safe, TTL) and a fine choice **if** you want concurrency-safe writes from the ThreadPoolExecutor without manual locking — that's its one real advantage here. Decision: start with the **JSON-per-URL cache** (transparent, zero-dep, good enough — workers write distinct files so no lock contention); upgrade to `diskcache` only if cache write contention or volume becomes a real problem. Note the JSON-per-file approach sidesteps the concurrent-write issue that would otherwise favor diskcache.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Excel I/O | openpyxl | pandas | Heavy install (NumPy), silently coerces/mutates column types → violates AC2 "unverändert"; overkill for hundreds of rows |
| HTTP client | requests (installed) | httpx | Only wins with full async; would add a dep and an asyncio rewrite for no gain on threaded I/O-bound work |
| Retry/backoff | urllib3 Retry (no dep) | tenacity | tenacity nicer API but extra dep; urllib3 Retry already present and handles `Retry-After` |
| Concurrency | ThreadPoolExecutor (stdlib) | asyncio + aiohttp | Async only pays off at much higher concurrency; threads are simpler and fit `requests` |
| HTML parser | bs4 + lxml | bs4 + html.parser | html.parser viable zero-dep, but lxml is more robust on malformed real-world HTML (the whole target population) |
| .env loading | python-dotenv | manual os.environ parser | dotenv is the standard, trivial, zero transitive deps; manual parser only to hit literal zero-new-deps |
| Cache | JSON-per-URL (stdlib) | diskcache / shelve | shelve = opaque pickle; diskcache great but a dep — only needed if concurrent-write safety matters; per-file JSON avoids that |
| Company data | heuristic + optional Zefix | commercial credit API / scraping Zefix HTML | Paid APIs out of scope; HTML scraping fragile + ToS risk; public REST + heuristic fallback satisfies AC5 |
| Payment-power | heuristic primary, LLM/Zefix optional | LLM-only | Hard LLM dependency breaks no-key/no-network requirement and AC4/AC5 robustness |

## Installation

```bash
# Activate the existing venv first:
#   source .venv/bin/activate

# Already installed (verify): openpyxl, requests, beautifulsoup4
# Recommended new (small, justified):
pip install python-dotenv lxml

# Optional — ONLY if you implement the LLM tier (lazy-imported, not required to run):
# pip install anthropic        # or call the REST endpoint with requests instead
```

`requirements.txt` (core, mandatory):
```
openpyxl>=3.1.5
requests>=2.34.2
beautifulsoup4>=4.15.0
lxml>=6.1.1
python-dotenv>=1.2.2
```
Keep `anthropic`/`openai` in an optional `requirements-llm.txt` (or just a README note) so the base setup stays minimal and <5-min (AC9). All five core packages ship binary wheels for Python 3.14 on macOS/Linux → no compilation, fast install.

## Confidence & Verification Notes

| Claim | Confidence | Basis |
|-------|------------|-------|
| openpyxl preserves columns/types, no pandas needed | HIGH | Library behavior + AC2 reasoning; installed |
| requests + urllib3 Retry + ThreadPoolExecutor pattern | HIGH | Standard, well-documented; installed versions confirmed |
| bs4 + lxml for tolerant parsing | HIGH | Installed bs4; lxml 6.1.1 available with wheels |
| PSI v5 endpoint + params (strategy/category, keyless works) | HIGH | Google official docs (developers.google.com) |
| PSI keyed quota 25k/day, ~400/100s | HIGH | Google docs / multiple sources |
| PSI **keyless** exact anonymous quota | MEDIUM | Undocumented anonymous limit; mitigated by key + backoff + cache |
| Zefix base endpoint + `/company/search` POST | HIGH | Official Swagger + opendata.swiss |
| Zefix anonymous (no-auth) access works | **MEDIUM/LOW** | OGD license suggests open; wrapper shows USR/PWD → verify with a live probe before relying on it; heuristic fallback removes the risk |
| Anthropic SDK 0.109.1 / structured output via tools | HIGH | PyPI version confirmed; tool-use JSON is standard |
| Exact current model IDs (haiku-4-5 etc.) | MEDIUM | Verify against Anthropic models list at build time — IDs change |
| JSON-per-URL disk cache satisfies AC7/AC8 | HIGH | Design reasoning; stdlib only |

## Sources

- [PageSpeed Insights API — Get Started (Google)](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Method: pagespeedapi.runpagespeed (Google)](https://developers.google.com/speed/docs/insights/rest/v5/pagespeedapi/runpagespeed)
- [PageSpeed Insights API limits discussion (Google Groups)](https://groups.google.com/g/pagespeed-insights-discuss/c/dB7hWmGAGsw)
- [PageSpeed Insights API guide (DebugBear)](https://www.debugbear.com/blog/pagespeed-insights-api)
- [PSI secret rate limit (bjb.dev)](https://bjb.dev/log/20221009-pagespeed-api/)
- [Zefix REST API Swagger (admin.ch)](https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html)
- [Zefix — opendata.swiss (OGD license)](https://opendata.swiss/en/dataset/zefix-zentraler-firmenindex)
- [validitylabs/zefix wrapper README (auth nuance)](https://github.com/validitylabs/zefix/blob/main/README.md)
- Installed package versions verified locally via `.venv/bin/pip` on 2026-06-14
