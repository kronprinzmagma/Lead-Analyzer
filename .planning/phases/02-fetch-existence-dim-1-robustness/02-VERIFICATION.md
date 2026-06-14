---
phase: 02-fetch-existence-dim-1-robustness
verified: 2026-06-14T00:00:00Z
status: passed
score: 4/4 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
---

# Phase 2: Fetch + Existence (Dim 1) + Robustness — Verification Report

**Phase Goal:** Each row gets a real existence verdict from a live, never-crashing fetch; unreachable/parked/social sites score Website-Bedarf 5.
**Verified:** 2026-06-14
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Phase 2 Success Criteria + CLAUDE.md AC1/AC4/AC11)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 / BED-01 | Dim 1 really measured: reachability (http/https + www probing), parked, social, thin verdicts | ✓ VERIFIED | `existence.analyze` lead_analyzer/analyzers/existence.py:70-109 implements first-match priority over a real FetchResult (dead, WAF 403/406/429, 4xx/5xx, parked host/marker, social host, thin <300 words, ok). `normalize()` fetch.py:20-67 builds ordered https/www/http variants. Exercised by test_existence.py (8 defs → reachable/parked/social/thin/dead all asserted, NOT stubbed). |
| SC2 / ROB-01 | Edge cases (empty Kiosk, broken `htp://`, timeout, unreachable) never crash; no reachable site → Bedarf 5 | ✓ VERIFIED | Live sample run: Kiosk (empty URL) → 5, Nähatelier (`htp://naehatelier-sutter`) → 5. True-offline simulation (all fetches raise ConnectionError): 42/42 rows → Bedarf 5, exit 0, no crash. Code: pipeline.py:31-35 empty URL → 5 no fetch; scoring.py:30-31 dead-prefix → 5. Tests: test_empty_url_no_network, test_dead_unreachable_is_bedarf_5, test_timeout, test_sample_offline. |
| SC3 / ROB-02 | fetch hardening: timeout tuple, browser UA + de-CH, redirect/size limits, SSL-as-signal, 403/429 neutral | ✓ VERIFIED | fetch.py:112-186: `timeout=(config.timeout_connect, config.timeout_read)` (no default-timeout pitfall), browser UA + `Accept-Language: de-CH` headers, `session.max_redirects=10`, `stream=True` + 2 MB cap (_read_capped), encoding fallback `errors="replace"`, SSLError → verify=False refetch with `ssl_ok=False` (not crash), bare `except Exception` → never raises. 403/406/429 → gap "blockiert" NOT severe (existence.py:77-78). Tests: test_request_shape, test_ssl_signal, test_byte_cap_stops_reading, test_encoding_fallback, test_block_403_is_neutral_not_5 (asserts bedarf==3, != 5). |
| SC4 / ROB-03 | Per-row exception boundary isolates one bad row; run continues | ✓ VERIFIED | pipeline.py:28-47: entire analyze_row wrapped in `try/except Exception` → degraded RowResult(bedarf=5, reason="Fehler: ..."). `grep -c "except Exception" pipeline.py` == 1. Tests: test_row_boundary_degrades_not_raises (raising analyzer → scored row), test_run_continues_after_bad_row (one raising row → both rows still written, rows_processed==2). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| lead_analyzer/fetch.py | normalize() + never-raising fetch() | ✓ VERIFIED | `def normalize` ×1, `def fetch` ×1; substantive (187 lines), wired into pipeline. |
| lead_analyzer/analyzers/existence.py | pure Dim-1 verdict | ✓ VERIFIED | analyze() ×1, 7-rule priority, real bs4 parsing; imported by pipeline. |
| lead_analyzer/pipeline.py | analyze_row wires normalize→fetch→existence→bedarf, per-row boundary | ✓ VERIFIED | Rewritten; imports fetch, existence, scoring. |
| lead_analyzer/scoring.py | bedarf_from_dim1 with dead→5 override | ✓ VERIFIED | scoring.py:21-34; dead prefixes → 5, severe→4, gap/ok→3. |
| lead_analyzer/models.py | FetchResult carrier | ✓ VERIFIED | models.py:39-55 dataclass with all Dim-1..6 fields. |
| tests/conftest.py | autouse network block + fakes | ✓ VERIFIED | autouse fixture raises on un-mocked request; make_fetch_result + FakeResponse exported. |
| tests/test_fetch.py, test_existence.py, test_pipeline_dim1.py | offline unit + integration | ✓ VERIFIED | 19 + 8 + 14 test defs; all offline. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| pipeline.analyze_row | fetch.normalize/fetch | direct call | ✓ WIRED | pipeline.py:30,36 |
| pipeline.analyze_row | existence.analyze | direct call | ✓ WIRED | pipeline.py:37 |
| pipeline.analyze_row | scoring.bedarf_from_dim1 | direct call | ✓ WIRED | pipeline.py:38 |
| fetch.fetch | requests.Session.get | network seam | ✓ WIRED | fetch.py:139-147; sole network boundary, monkeypatched in tests |
| run() | analyze_row per row | list comprehension | ✓ WIRED | pipeline.py:58 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green, offline | `pytest tests/ -q` | 61 passed in 0.10s | ✓ PASS |
| Tool runs on sample, no crash | `python run.py data/sample_input.xlsx -o output/phase2_verify.xlsx` | 42 rows, exit 0 | ✓ PASS |
| Output integrity | openpyxl inspect | len_out==42==len_in; all scores int 1-5; sorted desc bedarf,zahl | ✓ PASS |
| Edge cases → 5 | inspect output | Kiosk (empty)→5, Nähatelier (`htp://`)→5 | ✓ PASS |
| True-offline never-crash | force every fetch to raise ConnectionError, run() | 42/42 → Bedarf 5, exit 0 | ✓ PASS |
| Un-mocked request blocked | test_network_blocked_by_default | AssertionError raised | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BED-01 | 02-01 | Dim 1 really measured | ✓ SATISFIED | existence.analyze + test_existence.py |
| ROB-01 | 02-02 | edge cases never crash, sensible score | ✓ SATISFIED | true-offline sim 42→5; sample edge rows 5 |
| ROB-02 | 02-02 | fetch hardening | ✓ SATISFIED | fetch.py timeout/UA/redirect/size/SSL; 403→3 |
| ROB-03 | 02-02 | per-row exception boundary | ✓ SATISFIED | pipeline try/except + run-continues test |

### Constraint Compliance

| Constraint | Status | Evidence |
|------------|--------|----------|
| No thread pool / cache added | ✓ HELD | grep finds only inert future-phase config fields (workers, use_cache) + doc comments; no active concurrency/cache code in lead_analyzer/ |
| zahl stays placeholder | ✓ HELD | pipeline._zahl_placeholder → scoring.placeholder_result (constant 3); test_zahl_stays_placeholder |
| Tests fully offline | ✓ HELD | conftest autouse blocks network; un-mocked request raises (test_network_blocked_by_default) |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none | — | No TODO/FIXME/stub/NotImplemented in lead_analyzer/ |

### Honesty Review (skeptical check for "done but not really")

- No tautological tests found. `test_block_403_is_neutral_not_5` asserts the meaningful inverse (`bedarf != 5 AND == 3`). SSL signal test verifies the actual two-call sequence `[True, False]`. Byte-cap test uses a 3 MB body and asserts truncation.
- `test_sample_offline` mocks fetch but injects a genuine dead host for Nähatelier and asserts both edge rows == 5 — not a trivial pass. Independently corroborated by a real live run and a true-offline simulation done during this verification.
- Provisional non-dead scoring (severe-not-dead=4, gap/ok=3) is openly documented as provisional pending Phase-3 aggregation; it does not weaken any Phase-2 gated criterion (the dead→5 override is deterministic and verified).
- Thin-content threshold (300 words) flags many real SME homepages as gap→3; documented as tunable in Phase 3, does not affect edge-case→5 behavior.

### Gaps Summary

None. All four success criteria and all four requirements (BED-01, ROB-01, ROB-02, ROB-03) are satisfied in code, proven by 61 passing offline tests and confirmed by an independent live sample run, an output-integrity inspection, and a forced true-offline run (all 42 rows → Bedarf 5, zero crashes). Phase-1 regression intact (column passthrough, lossless sort, integer scores). Constraints held (no concurrency/cache, zahl placeholder, offline tests).

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
