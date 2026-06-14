---
phase: 07-hardening-readme-full-sample-run
verified: 2026-06-14T20:15:00Z
status: passed
score: 11/11 acceptance criteria verified (AC1-AC11) + DoD §7 + SETUP-01/02/03
re_verification:
  previous_status: none
  previous_score: n/a
overrides_applied: 0
gaps: []
human_verification: []
notes:
  - "Doc drift (cosmetic, non-blocking): README.md:117 and rationale say '202 tests'; actual suite is 205 passing."
  - "Dead code (cosmetic, non-blocking): scoring.py:21 DIM3_PLACEHOLDER is defined but never referenced; real Dim 3 is wired via performance.analyze in pipeline.py:73."
  - "Scope deferral (documented, AC-compliant): seo.py omits robots.txt/sitemap.xml HTTP probes (seo.py:11-13). AC11 only mandates dims 1-4 'really measured'; dim 4 measures title/meta/canonical/H1/noindex from the single fetch, which satisfies AC11."
---

# Phase 7 + Whole-Project DoD Verification Report

**Phase Goal:** The tool is set-up-and-run in under 5 minutes and produces a justified full-sample output, including edge cases. (Plus binding AC1-AC11 + DoD §7.)
**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial final sign-off

## Evidence Base (commands actually run)

- `python -m pytest tests/ -q` → **205 passed in 0.33s**
- `rm -rf /tmp/dodcache output/dod_verify.xlsx; python run.py data/sample_input.xlsx -o output/dod_verify.xlsx --no-cache` → **EXIT=0, "42 Zeilen verarbeitet (URL-Spalte: 'Website')"**
- openpyxl inspection of `output/dod_verify.xlsx`: 42 rows, headers, score columns, sort, edge cases
- Error path: file with no URL column → clear German error, EXIT=0 (no traceback)
- Resume test: `-n 6` run wrote 6 cache files; re-run produced **byte-identical** output
- `git ls-files | grep -iE 'env|output|cache'` → only `.env.example`, source/test files, planning docs tracked; **no `.env`, no output data, no cache data**
- `python -c "import os; print(bool(os.environ.get('PAGESPEED_API_KEY')))"` → **False** (run is genuinely zero-key)

## AC-by-AC Result

| AC | Criterion | Status | Evidence |
|----|-----------|--------|----------|
| AC1 | Vollständigkeit — whole list, no per-row intervention | ✓ PASS | Cold run processed all 42 rows in one command; ThreadPoolExecutor fan-out (pipeline.py:117-122); per-row boundary keeps run going (pipeline.py:84-94); "Pool hat eine Zeile verloren" guard (pipeline.py:125) |
| AC2 | Output form — original cols unchanged + exactly 2 int score cols (1-5, never empty); stable sort loses no rows | ✓ PASS | OUT headers = 5 original (unchanged order) + `Website-Bedarf (1-5)`, `Zahlungskräftigkeit (1-5)`, `Begründung`. All scores `int`, 1-5, **0 empties**. 42 in = 42 out, row name-set preserved. Sorted desc by (Bedarf,Zahl) = True. stable_sort tiebreak on index (scoring.py:85) |
| AC3 | Score direction monotonic (both) | ✓ PASS | `bedarf()` uses max(G-band, S-band) → adding a gap can only raise/hold (scoring.py:28-42). Direction tests: test_monotonic_worsening_gradient (test_scoring_bedarf.py:78, asserts `seq == sorted(seq)`), test_direction_monotone (test_payment.py:180). `dead`-flag override on flag not text (scoring.py:36) |
| AC4 | Robustness — invalid/missing/unreachable/timeout/parked/social → no crash, sensible score + note | ✓ PASS | Kiosk (empty URL) → Bedarf 5 "keine Website"; Nähatelier (`htp://`) → Bedarf 5 "nicht erreichbar; ungültiges SSL". No-URL-column file → clean error, no crash. Per-row try/except boundary → Bedarf 5 + conservative zahl (pipeline.py:84-94). fetch.py hard timeouts; PSI never raises (pagespeed.py:110 "Wirft NIE") |
| AC5 | Zahlungskräftigkeit from public signals, documented estimate, conservative+flagged | ✓ PASS | payment.py legal form (word-bounded AG/SA case-sensitive Pitfall-16, GmbH/Einzelfirma re.I), branch tier, size signals; conservative default. Every Begründung carries `Zahl (Schätzung):` prefix (e.g. "Branchen-Tier (Annahme): Detailhandel → tief"). No invented facts — only name/branch/site signals |
| AC6 | Traceability — per-row signals for each score | ✓ PASS | `Begründung` column non-empty on **all 42 rows**; per-dimension verdicts (`Dim1…Dim6` ok/Lücke/schwere Lücke) + `→ Bedarf N` + Zahl assumptions. reasons.build (pipeline.py:82) |
| AC7 | Repeatable/resumable — per-URL cache, abort doesn't lose work | ✓ PASS | cache.py atomic tempfile.mkstemp + os.replace under lock (cache.py:79-83); cache-aside in fetch.py:127-136 (incremental put per URL). Resume test: 6 cache files written, re-run byte-identical. PSI namespaced cache (pagespeed.py:116) |
| AC8 | Limits — external API batching/retry/backoff, never aborts | ✓ PASS | pagespeed.py: Semaphore concurrency cap (line 99/152), per-run `_Budget` (lines 45-68), capped retries (3) with exponential backoff + jitter, **Retry-After honored** (lines 176-198), returns None on every failure → never aborts run. Single shared client per run (pipeline.py:108) |
| AC9 | Operation — single command in/out; README setup <5min incl .env; runs zero keys | ✓ PASS | `python run.py input -o output` single entry (run.py). README setup block (venv→pip→run) + CLI flag table + `.env` section all-optional. Cold run executed with `PAGESPEED_API_KEY` **unset** and succeeded (graceful degradation: from_config→None, pagespeed.py:92-96) |
| AC10 | Verification — runs on sample, edge cases plausible, rationale explains scores | ✓ PASS | Cold run on data/sample_input.xlsx = 42 scored rows. docs/sample_run_rationale.md documents distribution (matches run exactly: Bedarf 1:3/2:12/3:15/4:10/5:2; Zahl 1:3/2:9/3:10/4:7/5:13), both edge cases, and big-vs-small contrast (KMU Treuhandexperte GmbH B4/Z5 top lead vs Coiffure Heidi B1/Z1) |
| AC11 | Website-Bedarf from 6 dims (dims 1-4 really measured, 5/6 ≥heuristic); per-customer dims drove score | ✓ PASS | 6 analyzers substantive (existence/technical/performance/seo/ai_readiness/content, 66-163 LOC each). Dim1 reachability/parked/social (existence.py); Dim2 HTTPS/SSL/free-subdomain (technical.py); Dim3 viewport-always + optional Lighthouse (performance.py, wired pipeline.py:73); Dim4 title/meta/canonical/H1/noindex (seo.py). Dim5 JSON-LD/OG, Dim6 contact/freshness heuristic. Per-dim reasons in Begründung |

## DoD §7

| DoD element | Status | Evidence |
|-------------|--------|----------|
| Output xlsx: all original cols + 2 score cols, all rows scored incl. edge cases | ✓ PASS | 42/42 scored, edge cases at Bedarf 5, structure verified |
| README explains setup + invocation | ✓ PASS | README.md setup + run + flags + .env |
| AC1-AC10 met | ✓ PASS | All green above |

## Phase 7 Requirements

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| SETUP-01 | README <5min, .env, runs no-keys | ✓ SATISFIED | README.md:10-69; zero-key cold run succeeded |
| SETUP-02 | Full sample run + edge cases + rationale (AC10) | ✓ SATISFIED | docs/sample_run_rationale.md; reproduced distribution exactly |
| SETUP-03 | .env + outputs gitignored, local only (§6) | ✓ SATISFIED | .gitignore covers .env/output/cache; git ls-files shows only .env.example tracked |

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| scoring.py | 21 | `DIM3_PLACEHOLDER` defined, never referenced | ℹ️ Info | Dead code; real Dim 3 wired via performance.analyze (pipeline.py:73). No functional impact |
| README.md | 117 | "202 Tests" but actual = 205 | ℹ️ Info | Cosmetic doc drift; suite is 205 green |
| seo.py | 11-13 | robots.txt/sitemap.xml DEFERRED | ℹ️ Info | Documented; AC11 mandates dims 1-4 measured — dim 4 measures title/meta/canonical/H1/noindex, satisfies AC11 |

No blocker or warning anti-patterns. No stubs in any rendering/scoring path.

## Gaps Summary

None. All 11 binding acceptance criteria (AC1-AC11), the Definition of Done (§7), and Phase 7 requirements (SETUP-01/02/03) are verified against actual code and live runtime behavior. The three notes above are cosmetic/documented and do not affect goal achievement: a doc test-count drift (202 vs 205), dead-code constant, and an explicitly-deferred robots/sitemap probe that AC11 does not require.

---

_Verified: 2026-06-14T20:15:00Z_
_Verifier: Claude (gsd-verifier)_
