# Roadmap: Lead-Analyzer

## Overview

From a raw Excel/CSV customer list to a sorted, scored lead list. We build the smallest runnable end-to-end slice first (Excel in -> two integer scores -> Excel out over ~4 rows), then make it better each phase: a non-crashing live fetch with the existence override, the real six-dimension Website-Bedarf score, the Zahlungskräftigkeit estimate, caching + concurrency for hundreds of rows, the optional PageSpeed tier, and finally hardening with a <5-minute README and a full 42-row sample run. The tool is fully runnable end-to-end after Phase 1 and stays runnable — optional network/key tiers (PageSpeed) arrive late and degrade gracefully.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: E2E Skeleton + Excel I/O** - Smallest runnable slice: read sample, trivial scores, sorted xlsx out ✓ (verified, 15 tests green)
- [x] **Phase 2: Fetch + Existence (Dim 1) + Robustness** - Non-crashing live fetch; dead/parked/social -> Bedarf 5
- [x] **Phase 3: Real Website-Bedarf Score (Dims 2,4,5,6 + Aggregation)** - Deterministic 6-dimension score with traceable reasons
- [x] **Phase 4: Zahlungskräftigkeit Estimator** - Second score from legal form + branch tier + site-size signals
- [x] **Phase 5: Cache + Concurrency** - Resumable per-URL cache and threaded fetch for hundreds of rows (completed 2026-06-14)
- [x] **Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting** - Skippable PSI tier with backoff; viewport heuristic fallback
- [x] **Phase 7: Hardening + README + Full Sample Run** - <5-min setup, .env handling, full 42-row run with rationale
- [x] **Phase 8: Company Research (Zefix) for Zahlungskräftigkeit** - Authoritative legal form/status from the Swiss commercial register; gated like PageSpeed, degrades to the name-heuristic without creds (completed 2026-06-15)
- [x] **Phase 9: myWEBSITE Sales Arguments Sheet** - Second output worksheet turning each company's deficits into myWEBSITE features + concrete sales benefits (gain framing) (completed 2026-06-15)

## Phase Details

### Phase 1: E2E Skeleton + Excel I/O
**Goal**: A single command turns the sample file into a sorted output xlsx with all original columns plus two integer score columns.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: IO-01, IO-02, IO-03, IO-04, IO-05, IO-06, IO-07
**Success Criteria** (what must be TRUE):
  1. User runs one command (`input.xlsx -> output.xlsx`, with `--limit 4`) and gets an output file over the first ~4 sample rows without manual per-row work (AC9).
  2. Output contains every original column unchanged in original order, plus exactly `Website-Bedarf (1-5)` and `Zahlungskräftigkeit (1-5)`, both integer 1-5 and never empty (even if trivial/constant for now) (AC2).
  3. The URL column is detected tolerantly across name variants (URL/Website/Webseite/Web); a file with no recognizable URL column gives a clear error instead of crashing (AC2, AC4).
  4. Output is sorted descending by Bedarf then Zahlungskräftigkeit with no rows lost (`len(out) == len(in)`) (AC2).
**Plans**: TBD

### Phase 2: Fetch + Existence (Dim 1) + Robustness
**Goal**: Each row gets a real existence verdict from a live, never-crashing fetch; unreachable/parked/social sites score Bedarf 5.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: BED-01, ROB-01, ROB-02, ROB-03
**Success Criteria** (what must be TRUE):
  1. Dimension 1 (Existenz & Substanz) is really measured per row: reachability via http/https + www-variant probing, parked/placeholder detection, social-media-only detection (AC11).
  2. The two sample edge cases (empty URL "Kiosk", broken `htp://naehatelier-sutter`) plus timeouts and unreachable sites never crash the run and each gets a sensible score (no reachable site -> Bedarf 5) with a note (AC4).
  3. HTTP fetch uses hard timeouts, a browser-like User-Agent + de-CH headers, redirect/size limits, and captures SSL errors as a signal rather than crashing (AC4).
  4. One failing row or stage is isolated by a per-row exception boundary; the overall run continues to completion (AC1, AC4).
**Plans**: 2 plans
- [x] 02-01-PLAN.md — Test scaffold (offline network block) + FetchResult + pure normalize() + existence verdict
- [x] 02-02-PLAN.md — Never-crashing fetch() seam + analyze_row wiring (dead->5) + offline sample integration

### Phase 3: Real Website-Bedarf Score (Dims 2,4,5,6 + Aggregation)
**Goal**: The Website-Bedarf score is derived deterministically from all six dimensions with a per-customer traceable reason.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: BED-02, BED-04, BED-05, BED-06, BED-07, BED-08, NACH-01
**Success Criteria** (what must be TRUE):
  1. Dimensions 2 (HTTPS/SSL + free-subdomain) and 4 (title/meta/canonical/robots/sitemap/H1/noindex) are really measured; dimensions 5 (JSON-LD/Schema.org/OG) and 6 (contact/tel/mailto/Impressum/freshness) are at least heuristically measured from the single fetch (AC11).
  2. The six dimension verdicts aggregate deterministically into a 1-5 score per the bands in `docs/scoring_website_bedarf.md`, with "no reachable website -> 5" always overriding (AC3, AC11).
  3. Score direction is monotonic: more/larger gaps yield a higher Bedarf, and a modern site over all dimensions scores 1 (verified by direction tests) (AC3).
  4. Each customer has a traceable record (reason column and/or run-log) of which dimensions/signals drove the Bedarf score (AC6, AC11).
**Plans**: 4 plans
- [x] 03-01-PLAN.md — Dim 2 Technische Basis + Dim 4 SEO (really measured, BED-02/04)
- [x] 03-02-PLAN.md — Dim 5 KI-Readiness + Dim 6 Inhalt/Aktualität (heuristic, BED-05/06)
- [x] 03-03-PLAN.md — scoring.bedarf 6-dim aggregation + reasons.py (BED-07/08, NACH-01)
- [x] 03-04-PLAN.md — pipeline wiring: parse-once, 6 verdicts, Begründung, modern→1/broken→5
**UI hint**: no

### Phase 4: Zahlungskräftigkeit Estimator
**Goal**: Each customer gets a documented 1-5 Zahlungskräftigkeit estimate from public signals, clearly labelled as an estimate.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: ZK-01, ZK-02, ZK-03
**Success Criteria** (what must be TRUE):
  1. Each row gets a 1-5 estimate combining legal form from the company name (word-bounded AG/GmbH/Einzelfirma), a branch kaufkraft tier, and website size signals (multiple locations/team/careers) (AC5).
  2. Every estimate is labelled as an estimate with its driving signals/assumptions recorded (reason column and/or log); thin data falls back to a conservative score with no invented facts (AC5, AC6).
  3. Score direction is correct: higher = more purchasing power (AC3).
**Plans**: 3 plans
  - [x] 04-01-PLAN.md — RED: PaymentEstimate dataclass + full failing test matrix (groups A/B/C, combine, conservative default, Pitfall-16 misfire, direction, range)
  - [x] 04-02-PLAN.md — GREEN: analyzers/payment.py (legal form + branch tier + size signals → 1-5, conservative default)
  - [x] 04-03-PLAN.md — WIRE: reasons.build(payment) per-section cap + analyze_row real zahl on all three paths

### Phase 5: Cache + Concurrency
**Goal**: Runs are resumable and fast enough for hundreds of rows via a per-URL cache and threaded fetch.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: PERF-01, PERF-03
**Success Criteria** (what must be TRUE):
  1. Per-URL results are cached incrementally to disk with atomic temp-file + replace; a re-run skips already-analyzed URLs and an interrupted run does not discard completed work (AC7).
  2. The orchestrator fetches concurrently (thread pool) and processes hundreds of rows in reasonable time, with stages skippable via flag (AC1).
  3. Caching and concurrency preserve correctness: output still has all rows, correct sort, and unchanged original columns.
**Plans**: 2 plans
  - [x] 05-01-PLAN.md — Atomic per-URL cache (cache.py) + FetchResult serialization + cache-aside in fetch.fetch (PERF-01)
  - [x] 05-02-PLAN.md — ThreadPoolExecutor in run() (determinism-preserving) + --workers/--no-cache CLI flags + resume (PERF-03)

### Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting
**Goal**: PageSpeed enriches Dimension 3 when available, stays fully skippable, and never stalls or aborts the run.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: BED-03, PERF-02
**Success Criteria** (what must be TRUE):
  1. Dimension 3 (Mobile & Performance) uses viewport-meta always and PageSpeed/Lighthouse when available; without network/key it degrades to the heuristic with a note (AC11).
  2. The PageSpeed client exposes availability, uses batching/retry/backoff and respects rate limits / `Retry-After`, with a per-run budget and a `--no-pagespeed` flag (AC8).
  3. A PageSpeed error or quota limit lowers nothing and aborts nothing — the run completes with degraded but valid scores (AC8, AC4).
**Plans**: 5 plans
  - [x] 06-01-PLAN.md — Wave 0: RED test scaffolds (.env loader, performance analyzer, PSI client) + inversion-guard golden test + conftest make_ps_result
  - [x] 06-02-PLAN.md — stdlib .env loader + PsResult dataclass + --no-pagespeed flag (config/cli/models)
  - [x] 06-03-PLAN.md — performance.py Dim-3 analyzer: viewport baseline + Lighthouse refinement (inversion guard)
  - [x] 06-04-PLAN.md — clients/pagespeed.py optional PSI client: budget, semaphore, backoff, namespaced cache
  - [x] 06-05-PLAN.md — wire Dim 3 into pipeline (one shared client) + offline byte-identical regression

### Phase 7: Hardening + README + Full Sample Run
**Goal**: The tool is set-up-and-run in under 5 minutes and produces a justified full-sample output, including edge cases.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: SETUP-01, SETUP-02, SETUP-03
**Success Criteria** (what must be TRUE):
  1. README explains setup (optional API keys via `.env`) and the single command in under 5 minutes; the tool runs end-to-end with no keys via graceful degradation (AC9).
  2. A full run over all 42 rows of `data/sample_input.xlsx` scores every row plausibly, including the empty-URL Kiosk, broken-URL Nähatelier, and large-vs-small firm cases, with a short written rationale for why the example scores make sense (AC10).
  3. `.env` and outputs are gitignored and the tool works locally without leaking firm/personal data (CLAUDE.md §6).
**Plans**: 5 plans
- [x] 07-01-PLAN.md — README.md: setup <5min, one command, all CLI flags, .env/no-keys, scores + 6 dimensions (SETUP-01)
- [x] 07-02-PLAN.md — docs/sample_run_rationale.md: full 42-row distribution + AC10 rationale (edge cases + big-vs-small firm) (SETUP-02)
- [x] 07-03-PLAN.md — Privacy/scope hardening: gitignore audit + .env.example as only committed env file (SETUP-03)
- [x] 07-04-PLAN.md — Verification: full suite (202) + reproducible no-key full run + Definition-of-Done sign-off
- [x] 07-05-PLAN.md — Planning-state cleanup (REQUIREMENTS/ROADMAP traceability) + optional unreachable-reason dedup

### Phase 8: Company Research (Zefix) for Zahlungskräftigkeit
**Goal**: With Zefix credentials, each customer's Zahlungskräftigkeit is grounded in the official Swiss commercial register (authoritative legal form + status + canton), not guessed from the company name; without credentials the run is byte-identical to today's offline heuristic.
**Mode:** mvp
**Depends on**: Phase 4 (payment estimator), Phase 6 (client + budget/backoff patterns)
**Requirements**: DIFF-01 (activated; refines ZK-01/ZK-02), NACH-01, PERF-02
**Success Criteria** (what must be TRUE):
  1. With `ZEFIX_USER`/`ZEFIX_PASSWORD` set, each customer is looked up in Zefix; the authoritative legal form + status replace the name-string guess in Zahlungskräftigkeit Group A, and the source (Zefix detail URL) + confidence (`zefix`/`heuristik`/`nicht-gefunden`) + resolved legal_form/status flow into the JSONL run-log (AC5, AC6).
  2. Without credentials, `ZefixClient.from_config()` returns None and a full sample run is byte-identical to the current offline name-heuristic — zero-setup preserved (AC9).
  3. `lookup()` never raises and degrades to the heuristic on timeout / non-200 / zero match; an ambiguous (>1) match yields "nicht gefunden" rather than a wrong attribution, and capital/employees stay explicitly "unknown" — no invented facts (AC4, AC5).
  4. Zefix calls share a per-run budget + concurrency cap + Retry-After backoff and a `zefix-v1` cache namespace with negative-hit caching; an API error never aborts the run (AC7, AC8).
**Plans**: 2 plans
- [x] 08-01-PLAN.md — ZefixClient (gated, budget/backoff) + ZefixFacts + Config fields
- [x] 08-02-PLAN.md — Zefix score composition (Group A + status modifier) + pipeline wiring + run-log

### Phase 9: myWEBSITE Sales Arguments Sheet
**Goal**: The output .xlsx gains a second worksheet that turns each company's measured deficits into positive, sales-ready myWEBSITE arguments — one row per company: customer name, its deficits, and the myWEBSITE features that fix them with the concrete benefit (gain framing, not deficit framing).
**Mode:** mvp
**Depends on**: Phase 3 (six-dimension verdicts are the deficit source), Phase 1 (table_io output writer)
**Requirements**: DIFF-04 (activated), NACH-01
**Success Criteria** (what must be TRUE):
  1. The output .xlsx contains a second worksheet (e.g. "myWEBSITE-Argumente") alongside "Leads", with columns Kundenname | Defizite | myWEBSITE-Funktionen & Nutzen, one row per company, written in the same sorted order as the main sheet (AC2-consistent).
  2. Each company's listed deficits are exactly its non-ok dimension verdicts (same drivers as the Bedarf score), and each deficit maps to its myWEBSITE feature + concrete benefit via a deterministic, traceable mapping table — no LLM, no invented features (AC6, no invented facts à la AC5).
  3. A company with no deficits (modern site, Bedarf 1) gets an honest "keine akuten Defizite — Stärken halten" note instead of forced/empty arguments.
  4. The feature is fully offline/deterministic and adds no network calls; the existing "Leads" sheet (all original columns + two scores + sort) is byte-unchanged; CSV output still works (the argument sheet is xlsx-native — for CSV a companion `*_argumente.csv` is written or its absence is documented).
  5. Tests cover the dimension→feature/benefit mapping (each of the six dimensions) and the second-sheet structure/order.
**Plans**: 1 plan
- [x] 09-01-PLAN.md — mywebsite.py mapping+builder, second "myWEBSITE-Argumente" sheet in table_io, companion CSV, Wave 0 tests

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. E2E Skeleton + Excel I/O | 1/1 | Complete | 2026-06-14 |
| 2. Fetch + Existence + Robustness | 2/2 | Complete | 2026-06-14 |
| 3. Real Website-Bedarf Score | 4/4 | Complete | 2026-06-14 |
| 4. Zahlungskräftigkeit Estimator | 3/3 | Complete | 2026-06-14 |
| 5. Cache + Concurrency | 2/2 | Complete | 2026-06-14 |
| 6. Optional PageSpeed + Rate Limiting | 5/5 | Complete | 2026-06-14 |
| 7. Hardening + README + Full Sample Run | 5/5 | Complete | 2026-06-14 |
| 8. Company Research (Zefix) for Zahlungskräftigkeit | 2/2 | Complete   | 2026-06-15 |
| 9. myWEBSITE Sales Arguments Sheet | 1/1 | Complete | 2026-06-15 |
