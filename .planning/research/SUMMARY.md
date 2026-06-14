# Project Research Summary

**Project:** MyWEBSITE-Lead-Analyzer
**Domain:** Local Python CLI batch enricher — Excel/CSV of Swiss SME customers in → same table + two integer 1–5 score columns out, via per-URL live website analysis, optional PageSpeed/LLM/Zefix, with caching, retry/backoff, and graceful degradation
**Researched:** 2026-06-14
**Confidence:** HIGH

## Executive Summary

This is a **batch fan-out/fan-in CLI tool**, not a service: read rows, analyze each customer URL concurrently over a thread pool, aggregate signals into two integer scores, sort, and write back the same table plus two columns. Experts build this exact shape with the standard library plus a few small, well-known dependencies — `openpyxl` (xlsx, no pandas so original columns/types pass through untouched), `requests` + `urllib3.Retry` + `ThreadPoolExecutor` (I/O-bound concurrency), and `beautifulsoup4`+`lxml` (tolerant HTML parsing of low-quality target sites). All four are already installed; only `python-dotenv` and `lxml` need adding. PageSpeed Insights, Zefix, and an LLM are strictly **optional tiers** layered on top.

The single dominant architectural force is **graceful degradation + resumability**: every row must get a score with a traceable reason even with **no API keys and no network** (pure heuristic fallback), and a kill mid-run must not discard completed work. This is satisfied by (a) an **optional-source degradation contract** — PageSpeed/LLM/Zefix expose `is_available()` and return a tagged degraded verdict instead of crashing; (b) a **per-URL JSON cache written incrementally with atomic temp-file + `os.replace`** so re-runs skip done rows and never corrupt; and (c) a **per-row `try/except Exception` boundary** so one bad URL can never abort the run. The Website-Bedarf score is **deterministic**: six dimension analyzers (Existenz, Technik, Mobile/Performance, SEO, KI-Bereitschaft, Inhalt) each emit `ok`/`Lücke`/`schwere Lücke`, aggregated by gap-point bands into 1–5, with "no reachable site → 5" as a hard override. Zahlungskräftigkeit is a **documented estimate** combining legal-form-from-name + branch tier + website size signals (never invented facts), optionally upgraded by a live Zefix lookup.

The biggest risks are all variants of robustness failures: **`requests` has no default timeout** (must always pass `timeout=(5,10)`), **default User-Agent gets 403'd** (making good sites look dead and inverting the lead ranking), **SSL errors should become a Dim-2 signal, not a crash**, **score inversion/off-by-one** (modern sites must score 1, dead sites 5), **sorting that drops rows**, and **PageSpeed turning a 300-row run into hours of 429s** if treated as mandatory inline. Mitigation is well-understood for every one of these (catch-all per row, browser UA + de-CH headers, capture-then-degrade SSL, golden direction tests + clamp to [1,5], stable sort on preserved index, PSI as a budgeted optional post-pass). Confidence is HIGH across the board; the only real unknowns are PageSpeed's undocumented keyless quota and Zefix's anonymous-vs-credentialed access — both de-risked by being optional with heuristic fallbacks.

## Key Findings

### Recommended Stack

The stack is chosen for **graceful degradation**: a mandatory core that works offline per row, then network/keyed tiers that only improve scores when available. No pandas (it silently coerces types, violating AC2 "unverändert"). All retry/concurrency is stdlib or already-installed; new deps are minimal and ship Python 3.14 wheels for a <5-min setup. See STACK.md.

**Core technologies:**
- **Python 3.14 stdlib** (`concurrent.futures`, `ssl`, `urllib.parse`, `json`, `csv`, `argparse`, `logging`, `dataclasses`): concurrency, SSL-cert inspection, URL normalization, caching, CLI — reach for these before any dependency.
- **openpyxl 3.1.5**: read/write `.xlsx` preserving original cells/types/order by appending columns — avoids pandas type-mutation.
- **requests 2.34.2 + urllib3 Retry + ThreadPoolExecutor**: robust threaded HTTP fetch with backoff/timeout — no async rewrite, no extra dep.
- **beautifulsoup4 4.15.0 + lxml 6.1.1**: tolerant parsing of malformed real-world HTML — drives dims 1, 2, 4, 5, 6 from one fetch.
- **python-dotenv 1.2.2**: load optional `.env` API keys (AC9) — tiny, zero transitive deps.
- **Optional (lazy-imported, never required):** PageSpeed Insights API (Dim 3), Zefix PublicREST (Zahlungskräftigkeit upgrade), anthropic/openai or raw `requests` (qualitative Dim 6).

### Expected Features

The six Website-Bedarf dimensions translate to concrete, mostly-deterministic HTTP/HTML signals scored into 1–5 via a documented gap-point formula. Whole engine is **≤2 network calls per customer** (HTTP fetch + PSI), both cacheable. See FEATURES.md.

**Must have (table stakes — satisfy AC11; dims 1–4 really measured):**
- Excel/CSV in → out, tolerant URL-column detection, 2 score columns + optional Begründung
- Dim 1 Existenz: URL normalization, reachability, parked/social detection, **score-5 override**
- Dim 2 Technik: HTTPS/SSL validity, free-subdomain (wixsite/jimdo/…) detection
- Dim 3 Mobile/Perf: PSI (perf+seo) with **viewport-meta heuristic fallback**
- Dim 4 SEO: title/meta/canonical/robots/sitemap/noindex/H1
- Dim 5 KI-readiness: JSON-LD/Schema.org + OpenGraph (heuristic OK)
- Dim 6 Inhalt: contact form/`tel:`/`mailto:`/Impressum/freshness/generator (heuristic OK)
- Deterministic 1–5 aggregation with traceable reasons; Zahlungskräftigkeit A(legal form)+B(branch)+C(site size) with logged assumptions
- Per-URL JSON cache + retry/backoff

**Should have (competitive — optional enrichment):**
- PSI API key wiring (lifts keyless quota for hundreds of rows reliably)
- Zefix live lookup (turns name-based legal-form *assumption* into confirmed public fact)
- LLM qualitative layer for Dim 6 (richer Begründung)

**Defer (v2+):**
- Mobile screenshot capture (heavy Playwright dep)
- Per-dimension breakout columns

### Architecture Approach

A thin CLI builds a `Config` and calls one `run()` orchestrator that reads rows into ordered `RowRecord`s (index preserved), fans `analyze_row` out across `ThreadPoolExecutor`, collects, stable-sorts by `(-bedarf, -zahl, index)`, and writes. Each analyzer reads ONE shared `FetchResult` per URL (fetch-once-parse-many) behind a cache-aside layer; verdicts are the single source of truth feeding both scoring and reasons so score and explanation can never diverge. See ARCHITECTURE.md.

**Major components:**
1. `cli.py` / `config.py` — single entry point, argparse, `.env` (keys optional)
2. `pipeline.py` — orchestrator: read → fan-out → collect → stable sort → write
3. `table_io.py` — xlsx/csv I/O, tolerant URL-column detection, column passthrough
4. `fetch.py` + `cache.py` — normalize/GET/retry/timeout + per-URL atomic incremental JSON cache
5. `analyzers/` (one file per dimension) + `payment.py` — signals → `DimensionVerdict`
6. `clients/` (pagespeed, llm) — optional sources behind `is_available()` degradation contract
7. `scoring.py` + `reasons.py` — pure deterministic aggregation → ints + reason strings

### Critical Pitfalls

1. **One bad row aborts the whole run** — bare `except Exception` per row → fallback score + Vermerk, loop continues. Outer net must NOT be `except requests.X` only.
2. **No HTTP timeout hangs the run** — always `timeout=(5,10)`; treat Timeout as a normal scored outcome.
3. **Default UA gets 403'd, scoring good sites as dead** — set browser-like UA + `Accept-Language: de-CH`; distinguish 403/429 ("nicht bewertbar", neutral score) from real "no website".
4. **Inverted/off-by-one/non-integer scores** — single tested mapping per score, `int(round())` + clamp [1,5], "no website → 5" as final override, golden direction tests.
5. **PageSpeed as mandatory inline → hours of 429s** — strictly optional, budgeted post-pass, backoff + cache, `--no-pagespeed`; PSI error ≠ low score.
6. (Also critical) **SSL error must be a Dim-2 signal not a crash**; **sort must not drop rows** (`len(out)==len(in)` assertion); **cache must be per-URL atomic** for resumability; **openpyxl must append, not rebuild** (preserve leading zeros/types); **Zahlungskräftigkeit must be labelled estimate, never invented facts**.

## Implications for Roadmap

Based on research, suggested phase structure (follows CLAUDE.md §5 "tiny E2E first" and ARCHITECTURE.md build order):

### Phase 1: E2E Skeleton + Excel I/O
**Rationale:** GSD smallest runnable slice; the I/O boundary is where AC2/AC10 data-corruption pitfalls live, so lock it first.
**Delivers:** `cli.py` (argparse: input/output/`--limit`) → `table_io` read + tolerant URL-column detection → trivial constant scoring → write xlsx with two appended columns + stable sort. Runs on `data/sample_input.xlsx --limit 4`.
**Addresses:** Excel/CSV in→out, URL-column detection, 2 score columns (AC2, AC9)
**Avoids:** Pitfall 13 (column/type loss — append don't rebuild), 14 (URL-column variants), 10 (sort drops rows)

### Phase 2: Models + Fetch + Existence (Dim 1) + Robustness Net
**Rationale:** The central AC1/AC4 robustness contract; everything downstream depends on a non-crashing, normalized fetch.
**Delivers:** `models.py`, `fetch.py` (normalize + GET + `timeout` + try/except + browser UA + size cap + SSL capture), `analyzers/existence.py` with score-5 override. The two sample edge cases (empty URL, `htp://…`) score sensibly.
**Uses:** requests + urllib3 Retry (STACK.md)
**Avoids:** Pitfalls 1–7 (one-row crash, no timeout, 403 UA, http/www permutations, huge pages, redirect/encoding, SSL-as-signal)

### Phase 3: Cache + Concurrency
**Rationale:** Required before scaling to hundreds of rows and before any rate-limited API; resumability must exist before long runs.
**Delivers:** `cache.py` (per-URL JSON, atomic temp+`os.replace`, incremental, thread-safe, normalized key, logic-version stamp, `--no-cache`); switch orchestrator to `ThreadPoolExecutor`. Re-run skips cached URLs.
**Implements:** fetch+cache lower layer, fan-out/fan-in (ARCHITECTURE.md)
**Avoids:** Pitfalls 11 (partial-write corruption), 12 (stale cache / key collision)

### Phase 4: Deterministic Dimensions 2,4,5,6 + Aggregation + Reasons
**Rationale:** Core scoring value; dims 1–4 must be really measured (AC11); aggregation correctness gates the entire deliverable.
**Delivers:** technical/seo/ai_readiness/content analyzers, `scoring.bedarf` gap-point aggregation with override, reason column + run-log.
**Addresses:** Dims 2/4/5/6 features (FEATURES.md)
**Avoids:** Pitfall 9 (inverted/off-by-one/non-int — with golden direction tests), 6 (German keyword/encoding handling for Dim 6)

### Phase 5: Zahlungskräftigkeit Estimator
**Rationale:** Second score, independent of website fetch (uses name + Branche + site signals); honesty constraints (AC5) need dedicated care.
**Delivers:** legal-form-from-name (word-bounded regex) + branch tier table + website size signals, with labelled assumptions and conservative thin-data default.
**Addresses:** Zahlungskräftigkeit heuristic A+B+C (AC5, AC6)
**Avoids:** Pitfalls 15 (hallucinated facts), 16 (legal-form misfire — `\bAG\b` not substring, combine with branch)

### Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting
**Rationale:** First optional tier; must come after core works without it so it stays strictly skippable.
**Delivers:** `clients/pagespeed.py` with `is_available()`, semaphore + backoff on 429, per-run budget, `--no-pagespeed`; degrades to viewport heuristic.
**Avoids:** Pitfall 8 (PSI quota/latency stalling the run)

### Phase 7: Optional LLM Layer (Dim 6 qualitative) + `--no-llm`
**Rationale:** Last additive enrichment; runs only with a key, after deterministic checks, never the sole basis for a score.
**Delivers:** `clients/llm.py` (lazy import, key guard, temp=0, robust JSON extraction, cache).
**Avoids:** Pitfall 17 (LLM JSON/key/nondeterminism)

### Phase 8: Hardening + README + Full Sample Run
**Rationale:** Final polish to AC9/AC10; verify full 42-row sample incl. edge cases, write the "why scores are sensible" rationale.
**Delivers:** `--workers`/`--no-cache` flags, `.env.example`, progress output, README <5 min, gitignore verification, AC10 write-up.
**Avoids:** Pitfall 18 (commit `.env`/output, scope creep), UX pitfalls (silent long run, README friction)

### Phase Ordering Rationale

- **Dependency-driven:** fetch underpins all dimension analyzers; cache must precede scaled/optional-API work; aggregation needs all deterministic verdicts. Optional tiers (PSI, LLM) come last because the degradation contract requires the core to be complete and self-sufficient first.
- **Architecture-driven:** grouping mirrors ARCHITECTURE.md's layered shape (I/O boundary → fetch/cache lower layer → analyzers → scoring → optional clients).
- **Pitfall-driven:** the I/O boundary (Phase 1) and the robustness net (Phase 2) are front-loaded because the most damaging pitfalls (silent column corruption, run-aborting crashes) are cheapest to prevent at the boundary and most expensive to retrofit.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 6 (PageSpeed):** verify keyless anonymous quota behavior and exact 429/`Retry-After` handling with a live probe; PSI response-field paths should be confirmed against current API.
- **Phase 5/extension (Zefix, if pursued):** **must do a live curl probe** — anonymous vs credentialed access is unresolved from docs (OGD license suggests open; wrapper README shows USR/PWD). Heuristic fallback removes the blocker either way.
- **Phase 7 (LLM):** confirm current Anthropic model IDs (e.g. haiku-4-5) at build time; verify structured-output/tool-use JSON shape.

Phases with standard patterns (skip research-phase):
- **Phase 1–4:** well-documented stdlib + openpyxl/requests/bs4 patterns; fan-out/fan-in, cache-aside, atomic write are all established idioms.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core deps installed + version-verified; only keyless-PSI quota and Zefix auth are MEDIUM, both optional with fallbacks |
| Features | HIGH | Dims 1–6 are deterministic HTTP/HTML facts mapped to a documented rubric; PSI thresholds + Zahlungskräftigkeit tiers are estimates by design (AC5) |
| Architecture | HIGH | Standard-library batch-pipeline patterns; no novel/uncertain tech |
| Pitfalls | HIGH | `requests`/openpyxl/PSI/LLM failure modes are stable and well-documented; each mapped to an AC and a phase |

**Overall confidence:** HIGH

### Gaps to Address

- **PageSpeed keyless quota (MEDIUM):** undocumented anonymous limit. Handle via free `.env` key as default, hard call budget, backoff + cache, and viewport-meta fallback. No blocker.
- **Zefix anonymous access (MEDIUM/LOW):** unresolved auth requirement. Handle by treating Zefix as best-effort optional, probing with one live curl before wiring in, optional `.env` credentials, and name-based heuristic baseline that satisfies AC5 with zero external dependency.
- **Exact LLM model IDs (MEDIUM):** verify against Anthropic models list at build time; IDs evolve. No design impact (lazy-imported, optional).
- **Branch/legal-form tier weights (by design, MEDIUM):** these are documented estimates per AC5, not facts — keep the lookup table transparent and editable, sales can override.

## Sources

### Primary (HIGH confidence)
- Project spec `CLAUDE.md` (AC1–AC11, §6), `docs/scoring_website_bedarf.md` (6-dimension rubric), `.planning/PROJECT.md` — authoritative requirements
- [Google PageSpeed Insights API v5 docs](https://developers.google.com/speed/docs/insights/v5/get-started) — endpoint, params, response shape (`lighthouseResult.categories.*.score`, `audits.*.numericValue`, `loadingExperience.metrics`), keyed quota 25k/day ~400/100s
- Python stdlib `concurrent.futures`, `ssl`, `csv`; `requests`, `openpyxl`, `beautifulsoup4`/`lxml` official docs — concurrency, SSL inspection, no-default-timeout footgun, append-columns preservation
- Cache-aside + atomic `os.replace` write; exponential backoff with jitter — established resilience idioms
- Installed package versions verified locally via `.venv/bin/pip` on 2026-06-14

### Secondary (MEDIUM confidence)
- [DebugBear: PageSpeed Insights API](https://www.debugbear.com/blog/pagespeed-insights-api) — field reference corroboration
- [PSI keyless rate-limit notes (bjb.dev, Google Groups)](https://bjb.dev/log/20221009-pagespeed-api/) — undocumented anonymous quota
- [Zefix REST Swagger (admin.ch)](https://www.zefix.admin.ch/ZefixPublicREST/swagger-ui/index.html) + [opendata.swiss OGD dataset](https://opendata.swiss/en/dataset/zefix-zentraler-firmenindex) — endpoint + license
- [Free website builders lists](https://www.sitebuilderreport.com/free-website-builders) — confirmed default subdomains for Dim 2
- LLM JSON-mode/structured-output failure modes (Anthropic/OpenAI docs) — fenced output, key-absence, nondeterminism

### Tertiary (LOW confidence)
- [validitylabs/zefix wrapper README](https://github.com/validitylabs/zefix/blob/main/README.md) — auth nuance (USR/PWD); needs live-probe validation
- Exact current Anthropic model IDs — verify at build time

---
*Research completed: 2026-06-14*
*Ready for roadmap: yes*
