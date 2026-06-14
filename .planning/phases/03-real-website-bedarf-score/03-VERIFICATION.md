---
phase: 03-real-website-bedarf-score
verified: 2026-06-14T00:00:00Z
status: passed
score: 4/4 truths verified
overrides_applied: 0
re_verification:
  previous_status: none
human_verification: []
---

# Phase 3: Real Website-Bedarf Score Verification Report

**Phase Goal:** The Website-Bedarf score is derived deterministically from all six dimensions with a per-customer traceable reason.
**Verified:** 2026-06-14
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Dims 2 (HTTPS/SSL+free-subdomain) & 4 (title/meta/canonical/robots/H1/noindex) really measured; dims 5 (JSON-LD/OG/microdata) & 6 (contact/tel/mailto/Impressum/freshness) heuristically measured from single fetch | ✓ VERIFIED | technical.py:43-66 reads `final_url` scheme/`ssl_ok`/host vs FREE_SUBDOMAIN set; seo.py:37-94 reads soup title/meta-desc/H1/canonical/lang + X-Robots header; ai_readiness.py:32-78 parses ld+json `@type`, og:* metas, itemscope; content.py:55-130 scans forms/tel/mailto/Impressum/Copyright/generator. Unit tests fire each signal (test_technical 9, test_seo 10, test_ai_readiness 8, test_content 10). Live run shows real per-dim notes (e.g. "Dim4 Lücke (keine Meta-Description; 14× H1)"). |
| 2 | Six verdicts aggregate deterministically into 1-5 per docs bands; "no reachable website → 5" always overrides | ✓ VERIFIED | scoring.bedarf scoring.py:28-42 — `if any(v.dead): return 5` is the FIRST check (non-bypassable), then pure G/S band math (no I/O, no randomness). Band probe: all-ok→1, 1gap→2, 2gap→3, 4gap→4, 3severe→5; dead-override with all-ok→5. Matches doc §Aggregation; doc explicitly delegates exact formula to implementation. |
| 3 | Monotonic direction: more/larger gaps → higher Bedarf; modern site → 1; verified by direction tests | ✓ VERIFIED | `max(g_score, s_score)` with severe=2pts guarantees monotonicity by construction. test_scoring_bedarf::test_monotonic_worsening_gradient asserts `seq == sorted(seq)` over 12-step worsening; test_modern_site_is_bedarf_1 + test_direction_gradient_non_decreasing (pipeline). NOT tautological: live run over 42 real sites gives a genuine spread {1:3, 2:12, 3:15, 4:10, 5:2}. |
| 4 | Each customer has a traceable record of which dims/signals drove the score | ✓ VERIFIED | reasons.build reasons.py:19-39 lists every non-ok/dead dim with level+reason + computed Bedarf note, capped 200 chars; score recomputed from same verdicts (single source of truth). Wired in pipeline.py:62; table_io writes `Begründung` column (default on, config.py:19, table_io.py:24/176). Output file inspected: all 42 rows have non-empty per-dim reasons. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| analyzers/technical.py | Dim 2 real measurement | ✓ VERIFIED | 66 lines, reads ssl_ok/scheme/host; endswith-guard against evilwix; wired pipeline.py:54 |
| analyzers/seo.py | Dim 4 real measurement | ✓ VERIFIED | 94 lines; parse-once contract (takes soup, never builds it); robots.txt/sitemap deferred to Phase 5/6 (documented), dims 1-4 still real per AC11 |
| analyzers/ai_readiness.py | Dim 5 heuristic | ✓ VERIFIED | 78 lines; defensive JSON parse; wired pipeline.py:56 |
| analyzers/content.py | Dim 6 heuristic | ✓ VERIFIED | 130 lines; soup=None guard before fr.html scan; wired pipeline.py:57 |
| scoring.py::bedarf | Deterministic aggregation | ✓ VERIFIED | dead-override first, then G/S bands |
| reasons.py::build | Traceable reason | ✓ VERIFIED | wired pipeline.py:62, output column |
| pipeline.py | parse-once wiring of 6 verdicts | ✓ VERIFIED | soup built once (line 50), shared to dims 1/4/5/6; per-row boundary line 64 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| pipeline.analyze_row | scoring.bedarf | direct call line 59 | ✓ WIRED | 6 verdicts → int score |
| pipeline.analyze_row | reasons.build | direct call line 62 | ✓ WIRED | reason stored on RowResult |
| pipeline | shared soup → dims 4/5/6 | BeautifulSoup once line 50 | ✓ WIRED | parse-once; existence copies tree before decompose (existence.py:103) so shared soup is NOT corrupted — verified empirically |
| RowResult.reason | output Begründung col | table_io._row_values | ✓ WIRED | value written per row, default-on |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `pytest tests/ -q` | 134 passed in 0.19s | ✓ PASS |
| Offline-forced 42-row run | forced-dead fetch via pipeline.run | 42 rows, all bedarf==5, no crash, all reasons populated | ✓ PASS |
| Parse-once mutation safety | run existence then seo/ai/content on shared soup | title+footer intact; dims 4/5/6 all "ok" on modern fixture | ✓ PASS |
| Live best-effort run | `python run.py data/sample_input.xlsx -o ...` | 42 rows, real gradient {1:3,2:12,3:15,4:10,5:2}, all int 1-5, all reasons | ✓ PASS |
| 403-no-body invariant | test_block_403_no_body_is_not_5_and_is_2 | bedarf==2, never 5 | ✓ PASS |
| Band boundaries | scoring.bedarf probes | 1/2/3/4/5 + dead-override→5 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BED-02 | 03-01 | Dim 2 technische Basis real | ✓ SATISFIED | technical.py + test_technical.py |
| BED-04 | 03-01 | Dim 4 SEO real | ✓ SATISFIED | seo.py + test_seo.py (robots.txt/sitemap deferred, documented) |
| BED-05 | 03-02 | Dim 5 KI-readiness heuristic | ✓ SATISFIED | ai_readiness.py + test_ai_readiness.py |
| BED-06 | 03-02 | Dim 6 Inhalt/Aktualität heuristic | ✓ SATISFIED | content.py + test_content.py |
| BED-07 | 03-03 | Deterministic 6-dim aggregation per doc bands; dead→5 | ✓ SATISFIED | scoring.bedarf + test_scoring_bedarf |
| BED-08 | 03-03 | Monotonic direction | ✓ SATISFIED | max(g,s) bands + monotonic gradient tests + live spread |
| NACH-01 | 03-03/04 | Per-customer traceable signals | ✓ SATISFIED | reasons.build + Begründung column |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| scoring.py | 21 | DIM3_PLACEHOLDER (level=ok) | ℹ️ Info | Intentional — Dim 3 (PageSpeed) is Phase 6 by roadmap; neutral 0-pt placeholder, documented. Not a Phase-3 gap. |
| pipeline.py | 23-25 | zahl placeholder | ℹ️ Info | Zahlungskräftigkeit is Phase 4 by roadmap; test_zahl_stays_placeholder confirms expected. Not a Phase-3 gap. |
| seo.py | 11-13 | robots.txt/sitemap omitted | ℹ️ Info | Explicitly deferred (needs extra HTTP+cache, Phase 5/6). AC11 satisfied: dims 1-4 measured; title/meta/canonical/H1/noindex/lang all real. |

### Human Verification Required

None. All four observable truths are verifiable programmatically and were confirmed via tests + offline and live sample runs.

### Calibration Concern (forward note — does NOT fail Phase 3)

existence.py:67 `_THIN_WORDS = 300`: homepages with under 300 visible words (after stripping script/style/nav/footer) are flagged "dünner Inhalt" → Dim 1 gap, adding a gap point. Many legitimate Swiss SME single-page/landing-style homepages legitimately render under 300 words, which can inflate Bedarf for solid sites. This is a calibration/tuning question, not a correctness defect (the score remains deterministic, monotonic, and traceable). **Recommend revisiting this threshold during Phase 7 SETUP-02 (hardening + full sample run rationale)** when the full 42-row rationale is reviewed against ground truth.

### Gaps Summary

No gaps. The Website-Bedarf score is derived deterministically from all six dimensions (dims 1-4 really measured, 5-6 heuristic, 3 a documented Phase-6 placeholder), aggregated via a pure dead-override + G/S band function matching the doc, monotonic by construction and verified by a non-tautological live gradient, with a per-customer Begründung column listing the driving dimensions/signals. The revised "403-no-body ≠ 5" invariant holds (neutral no-HTML policy in dims 4/5/6 + existence WAF gap). Parse-once is correctly implemented with a defensive copy in existence before destructive decompose, so the shared soup is not corrupted. All 134 tests pass; prior-phase behavior (column passthrough, stable sort, zahl placeholder) intact.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
