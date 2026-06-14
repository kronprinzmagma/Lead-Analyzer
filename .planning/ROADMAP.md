# Roadmap: MyWEBSITE Lead-Analyzer

## Overview

From a raw Excel/CSV customer list to a sorted, scored lead list. We build the smallest runnable end-to-end slice first (Excel in -> two integer scores -> Excel out over ~4 rows), then make it better each phase: a non-crashing live fetch with the existence override, the real six-dimension Website-Bedarf score, the Zahlungskräftigkeit estimate, caching + concurrency for hundreds of rows, the optional PageSpeed tier, and finally hardening with a <5-minute README and a full 42-row sample run. The tool is fully runnable end-to-end after Phase 1 and stays runnable — optional network/key tiers (PageSpeed) arrive late and degrade gracefully.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: E2E Skeleton + Excel I/O** - Smallest runnable slice: read sample, trivial scores, sorted xlsx out ✓ (verified, 15 tests green)
- [ ] **Phase 2: Fetch + Existence (Dim 1) + Robustness** - Non-crashing live fetch; dead/parked/social -> Bedarf 5
- [ ] **Phase 3: Real Website-Bedarf Score (Dims 2,4,5,6 + Aggregation)** - Deterministic 6-dimension score with traceable reasons
- [ ] **Phase 4: Zahlungskräftigkeit Estimator** - Second score from legal form + branch tier + site-size signals
- [ ] **Phase 5: Cache + Concurrency** - Resumable per-URL cache and threaded fetch for hundreds of rows
- [ ] **Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting** - Skippable PSI tier with backoff; viewport heuristic fallback
- [ ] **Phase 7: Hardening + README + Full Sample Run** - <5-min setup, .env handling, full 42-row run with rationale

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
**Plans**: TBD
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
**Plans**: TBD

### Phase 5: Cache + Concurrency
**Goal**: Runs are resumable and fast enough for hundreds of rows via a per-URL cache and threaded fetch.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: PERF-01, PERF-03
**Success Criteria** (what must be TRUE):
  1. Per-URL results are cached incrementally to disk with atomic temp-file + replace; a re-run skips already-analyzed URLs and an interrupted run does not discard completed work (AC7).
  2. The orchestrator fetches concurrently (thread pool) and processes hundreds of rows in reasonable time, with stages skippable via flag (AC1).
  3. Caching and concurrency preserve correctness: output still has all rows, correct sort, and unchanged original columns.
**Plans**: TBD

### Phase 6: Optional PageSpeed (Dim 3) + Rate Limiting
**Goal**: PageSpeed enriches Dimension 3 when available, stays fully skippable, and never stalls or aborts the run.
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: BED-03, PERF-02
**Success Criteria** (what must be TRUE):
  1. Dimension 3 (Mobile & Performance) uses viewport-meta always and PageSpeed/Lighthouse when available; without network/key it degrades to the heuristic with a note (AC11).
  2. The PageSpeed client exposes availability, uses batching/retry/backoff and respects rate limits / `Retry-After`, with a per-run budget and a `--no-pagespeed` flag (AC8).
  3. A PageSpeed error or quota limit lowers nothing and aborts nothing — the run completes with degraded but valid scores (AC8, AC4).
**Plans**: TBD

### Phase 7: Hardening + README + Full Sample Run
**Goal**: The tool is set-up-and-run in under 5 minutes and produces a justified full-sample output, including edge cases.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: SETUP-01, SETUP-02, SETUP-03
**Success Criteria** (what must be TRUE):
  1. README explains setup (optional API keys via `.env`) and the single command in under 5 minutes; the tool runs end-to-end with no keys via graceful degradation (AC9).
  2. A full run over all 42 rows of `data/sample_input.xlsx` scores every row plausibly, including the empty-URL Kiosk, broken-URL Nähatelier, and large-vs-small firm cases, with a short written rationale for why the example scores make sense (AC10).
  3. `.env` and outputs are gitignored and the tool works locally without leaking firm/personal data (CLAUDE.md §6).
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. E2E Skeleton + Excel I/O | 0/TBD | Not started | - |
| 2. Fetch + Existence + Robustness | 0/2 | Not started | - |
| 3. Real Website-Bedarf Score | 0/TBD | Not started | - |
| 4. Zahlungskräftigkeit Estimator | 0/TBD | Not started | - |
| 5. Cache + Concurrency | 0/TBD | Not started | - |
| 6. Optional PageSpeed + Rate Limiting | 0/TBD | Not started | - |
| 7. Hardening + README + Full Sample Run | 0/TBD | Not started | - |
