---
phase: 08-company-research-zefix-for-zahlungskr-ftigkeit
verified: 2026-06-15T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run with live ZEFIX_USER/ZEFIX_PASSWORD credentials against a known Swiss company (e.g. Muster AG, canton ZH) and confirm the JSONL run-log shows confidence: zefix, a valid legal_form, status: ACTIVE, and a resolving source_url like https://www.zefix.admin.ch/de/search/entity/{ehraid}/info"
    expected: "The zahl_signals entry in the run-log contains 'Zefix', 'autoritativ', and the CHE-... UID; the score differs from the name-heuristic baseline for a company whose name does not contain AG/GmbH/etc."
    why_human: "Requires live Zefix API credentials (obtained by emailing zefix@bj.admin.ch) and a network call to the production API; offline unit tests cover all code paths but cannot verify that the API contract (field names, status enum, Basic Auth) is still correct in production."
---

# Phase 8: Company Research (Zefix) for Zahlungskräftigkeit — Verification Report

**Phase Goal:** With Zefix credentials, each customer's Zahlungskräftigkeit is grounded in the official Swiss commercial register (authoritative legal form + status + canton), not guessed from the company name; without credentials the run is byte-identical to today's offline heuristic.
**Verified:** 2026-06-15
**Status:** human_needed (all 4 automated SCs verified; 1 live-API smoke-test pending)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | With creds: authoritative legal form + status replace name guess in Group A; source_url + confidence + legal_form/status flow into JSONL run-log | VERIFIED | `payment.py:64-94` `_legal_form_from_zefix()` + `_status_modifier()` wired into `estimate()`; `zahl_signals` (carrying `source_url`, `uid`, "Zefix", "autoritativ") flow to `RowResult.zahl_signals` (`pipeline.py:96-99`) and then to `table_io.write_run_log` line 225; `test_zefix_ag_active` and `test_zefix_gmbh_cancelled` assert all of this end-to-end |
| SC2 | Without creds: `from_config()` returns None; full run is byte-identical to offline heuristic; no network called | VERIFIED | `zefix.py:99-119`: returns None unless both `ZEFIX_USER` and `ZEFIX_PASSWORD` present; `test_unavailable_without_creds` asserts this; `pipeline.py:128` builds client once; `_zefix_facts()` closure returns None when client is None; `test_zefix_none_fallback` asserts field-by-field byte-identity of `estimate()` output |
| SC3 | `lookup()` never raises; 0/>1 match → None; <3-char guard present; capital/canton stay absent (not invented) | VERIFIED | `zefix.py:125-165`: lookup() has no uncaught raises; `_parse()` (`zefix.py:213-248`) returns None unless `len(results) == 1`; name stripped at line 136, len<3 guard at line 137-138; `ZefixFacts` never sets capital/employees; `legalSeat` (commune name, not canton abbrev) stored; all 10 unit tests verify no-raise contract |
| SC4 | Per-run budget + Semaphore + Retry-After backoff present and wired; `zefix-v1` cache namespace with negative-hit caching; transient errors NOT cached | VERIFIED | `_Budget` class at `zefix.py:54-79`; `threading.Semaphore` at line 115; `_backoff_delay` + `_parse_retry_after` at lines 251-278; cache key `["zefix-v1", name, canton or ""]` at line 141; negative hit `{"_miss": True}` at line 164; transient errors return None without `cache.put` (lines 155-157); `test_429_retry_capped`, `test_budget_exhausted`, `test_negative_cache_hit`, `test_cache_hit_no_network` all pass |

**Score:** 4/4 truths verified (automated)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lead_analyzer/clients/zefix.py` | ZefixClient with budget/backoff/cache | VERIFIED | 279 lines; substantive — `_Budget`, `ZefixClient`, `_parse`, `_backoff_delay`, `_parse_retry_after` all present and wired |
| `lead_analyzer/models.py` | `ZefixFacts` dataclass | VERIFIED | Lines 44-60; 7 JSON-native fields matching spec: `legal_form_de`, `legal_form_fr`, `status`, `uid`, `legal_seat`, `source_url`, `source="zefix"` |
| `lead_analyzer/config.py` | `use_zefix`, `zefix_concurrency`, `zefix_budget` fields | VERIFIED | Lines 67-69; `use_zefix: bool = True`, `zefix_concurrency: int = 2`, `zefix_budget: int = 200` |
| `lead_analyzer/analyzers/payment.py` | `estimate(zefix_facts=None)`, `_legal_form_from_zefix()`, `_status_modifier()` | VERIFIED | Lines 64-94 and 174; `_legal_form_from_zefix` maps `legal_form_de` to AG/SA=2, GmbH/Sàrl/Sarl/KlG/&=1, Einzelunternehmen=0; `_status_modifier` applies -1/-2 penalty post-aggregation clamped via `scoring.clamp_score` |
| `lead_analyzer/pipeline.py` | `ZefixClient` import, single-client build in `run()`, `zx_client` threaded into `analyze_row` | VERIFIED | Line 24 import; line 128 `from_config`; line 30 `analyze_row(... zx_client=None)`; line 138 pool submit passes both clients positionally |
| `tests/test_zefix_client.py` | 10 binding tests from 08-VALIDATION.md | VERIFIED | All 10 tests present with exact names from validation map; all pass |
| `tests/test_payment.py` | 3 new zefix tests (`test_zefix_ag_active`, `test_zefix_gmbh_cancelled`, `test_zefix_none_fallback`) | VERIFIED | Lines 261-297; all 3 pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `pipeline.run()` | `ZefixClient.from_config(config)` | `zefix.py:from_config` | WIRED | `pipeline.py:128`; returns None without creds |
| `analyze_row()` | `zx_client.lookup(name, canton)` | `_zefix_facts()` closure | WIRED | `pipeline.py:52-58`; guarded by `zx_client is None or not zx_client.is_available()` |
| `analyze_row()` | `payment.estimate(... zefix_facts=zefix_facts)` | keyword arg | WIRED | `pipeline.py:67` (empty-URL path) and `pipeline.py:95` (normal path); exception path intentionally omits Zefix (T-08-08) |
| `payment.estimate()` | `_legal_form_from_zefix(facts)` | branch on `zefix_facts is not None` | WIRED | `payment.py:190-193`; authoritative path replaces name heuristic |
| `_legal_form_from_zefix()` | `ZefixFacts.uid` in signal note | f-string | WIRED | `payment.py:79`: `f"Rechtsform {label} aus Zefix (autoritativ, Quelle: {facts.uid})"` |
| `_status_modifier()` | `ZefixFacts.source_url` in signal note | f-string | WIRED | `payment.py:91-93`: `source_url` appears in signals for BEING_CANCELLED and CANCELLED |
| `PaymentEstimate.signals` | `RowResult.zahl_signals` | `pipeline.py:99` | WIRED | `est.signals` assigned to `RowResult(... zahl_signals=est.signals)` |
| `RowResult.zahl_signals` | JSONL run-log | `table_io.write_run_log` | WIRED | `table_io.py:225`: `"zahl_signals": list(result.zahl_signals)` |
| `ZefixClient.lookup()` | `cache.put(ck, facts.__dict__)` | positive hit | WIRED | `zefix.py:162`: success path |
| `ZefixClient.lookup()` | `cache.put(ck, {"_miss": True})` | negative hit | WIRED | `zefix.py:164`: 0 or >1 results |
| transient error in `_request()` | NOT cached | absence of `cache.put` | WIRED | `zefix.py:155-157`: returns None before any `cache.put` call |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `payment.estimate()` → `est.signals` | `na` (Group A notes) | `_legal_form_from_zefix(zefix_facts)` when facts available | Yes — `facts.uid`, `facts.legal_form_de` from Zefix API response (or None from heuristic) | FLOWING |
| `RowResult.zahl_signals` | `est.signals` | `payment.estimate()` return value | Yes — passes through unchanged | FLOWING |
| JSONL run-log `zahl_signals` field | `result.zahl_signals` | `table_io.write_run_log` line 225 | Yes — serialized as list | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| from_config returns None without creds | `pytest tests/test_zefix_client.py::test_unavailable_without_creds -q` | PASSED | PASS |
| 1 result → ZefixFacts with correct parse paths | `pytest tests/test_zefix_client.py::test_single_match_parsed -q` | PASSED | PASS |
| 0 results → None, negative cached | `pytest tests/test_zefix_client.py::test_zero_results_none -q` | PASSED | PASS |
| >1 results → None, negative cached | `pytest tests/test_zefix_client.py::test_ambiguous_none -q` | PASSED | PASS |
| timeout → None, NOT cached | `pytest tests/test_zefix_client.py::test_timeout_none -q` | PASSED | PASS |
| 429 → retries capped at 3, sleep called >=1x | `pytest tests/test_zefix_client.py::test_429_retry_capped -q` | PASSED | PASS |
| budget=0 → None without network | `pytest tests/test_zefix_client.py::test_budget_exhausted -q` | PASSED | PASS |
| cache hit → return without network | `pytest tests/test_zefix_client.py::test_cache_hit_no_network -q` | PASSED | PASS |
| negative cache hit → None without network | `pytest tests/test_zefix_client.py::test_negative_cache_hit -q` | PASSED | PASS |
| name <3 chars → None without network | `pytest tests/test_zefix_client.py::test_short_name_guard -q` | PASSED | PASS |
| AG + ACTIVE → zahl=5, signals contain Zefix+autoritativ+uid | `pytest tests/test_payment.py::test_zefix_ag_active -q` | PASSED | PASS |
| GmbH + CANCELLED → zahl=2 (penalty applied), status in signals | `pytest tests/test_payment.py::test_zefix_gmbh_cancelled -q` | PASSED | PASS |
| zefix_facts=None → byte-identical to offline baseline | `pytest tests/test_payment.py::test_zefix_none_fallback -q` | PASSED | PASS |
| Full suite | `pytest -q` | 219 passed in 0.35s | PASS |

---

## Parse-Path Spot-Check (RESEARCH.md Contract)

RESEARCH.md specifies these exact parse paths:

| Field | Specified path | Implemented at | Match |
|-------|---------------|----------------|-------|
| Legal form short name DE | `r["legalForm"]["shortName"]["de"]` | `zefix.py:227` | EXACT |
| Legal form short name FR | `r["legalForm"]["shortName"]["fr"]` | `zefix.py:228` | EXACT |
| Status | `r["status"]` | `zefix.py:229` | EXACT |
| UID | `r.get("uid") or ""` | `zefix.py:230` | EXACT |
| Legal seat | `r.get("legalSeat") or ""` | `zefix.py:231` | EXACT |
| Source URL | `ehraid` → `https://www.zefix.admin.ch/de/search/entity/{ehraid}/info` | `zefix.py:232-237` | EXACT — constructed from integer `ehraid`, URL field NOT echoed (T-08-02 mitigated) |
| 1 result rule | `len(results) != 1 → None` | `zefix.py:223-224` | EXACT |

---

## Security Checks

| Concern | Check | Result |
|---------|-------|--------|
| Raw credentials never stored as instance attributes | `grep self\._user self\._password zefix.py` | PASS — only `self._auth` (base64) exists |
| Raw credentials never logged | Scan for logging calls in zefix.py | PASS — no `log`, `print`, `logger` calls that reference user/password |
| Credentials never reach payment.py or pipeline.py | Grep for ZEFIX_USER/ZEFIX_PASSWORD in those files | PASS — only appear in pipeline.py comments |
| source_url not echoed from response | `_parse()` constructs from `ehraid` integer | PASS — `zefix.py:232-237`; response URL field not used |
| Cache never stores credentials | `cache.put(ck, facts.__dict__)` where `ZefixFacts` has no auth fields | PASS — ZefixFacts contains only `legal_form_de/fr`, `status`, `uid`, `legal_seat`, `source_url`, `source` |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| DIFF-01 | Live-Zefix-Lookup for Zahlungskräftigkeit; gated; byte-identical without creds | SATISFIED | `ZefixClient.from_config` returns None without creds; `_legal_form_from_zefix` replaces name guess; `test_zefix_none_fallback` pins byte-identity |
| NACH-01 | Signals/assumptions visible in Begründungsspalte and/or run-log | SATISFIED | `PaymentEstimate.signals` → `RowResult.zahl_signals` → `table_io.write_run_log` line 225; uid, source_url, legal_form_de in signals |
| PERF-02 | External APIs use batching/retry/backoff; API error never aborts run | SATISFIED | `_Budget` + `threading.Semaphore` + `_backoff_delay` in `zefix.py`; `lookup()` never raises; `test_429_retry_capped` asserts capped retries |
| ZK-01 (refined by DIFF-01) | Score from public signals including legal form | SATISFIED | Zefix authoritative legal form replaces name regex in Group A when available |
| ZK-02 (refined by DIFF-01) | Schätzung marked, signals traceable, no invented facts | SATISFIED | capital/employees not in CompanyShort response → not fetched → not invented; `source="zefix"` label in signals; ambiguous match → None → heuristic (no wrong attribution) |

---

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `zefix.py:259-262` | `_backoff_delay` and `_parse_retry_after` duplicated from pagespeed.py | INFO | Intentional: 08-RESEARCH.md and 08-01-SUMMARY.md document this as a "future refactor candidate". Both copies marked with `# [COPIED VERBATIM from clients/pagespeed.py — future refactor candidate]`. Not a blocker. |

No TODO, FIXME, placeholder, `return {}`, `return []`, or stub patterns found in `zefix.py`, `payment.py` (Zefix sections), or `pipeline.py` (Zefix wiring).

---

## Human Verification Required

### 1. Live Zefix API Smoke Test

**Test:** With `ZEFIX_USER` and `ZEFIX_PASSWORD` set in `.env` (credentials from zefix@bj.admin.ch), run:
```
python -m lead_analyzer data/sample_input.xlsx /tmp/out_zefix.xlsx --limit 5
```
Then inspect the JSONL run-log (`/tmp/out_zefix.jsonl`) for rows where the company name was found in Zefix.

**Expected:**
- At least one row shows `"confidence": "zefix"` (or equivalent) in `zahl_signals`
- `zahl_signals` contains a string with `"Zefix"`, `"autoritativ"`, and a `CHE-...` UID
- `zahl_signals` contains a `source_url` like `https://www.zefix.admin.ch/de/search/entity/{ehraid}/info` that resolves in a browser
- A row for a company whose name contains no AG/GmbH suffix but whose Zefix record shows "AG" should receive a higher `zahl` than the offline heuristic would assign

**Why human:** Requires live API credentials and network access to `zefix.admin.ch`. All offline code paths are fully covered by the 13 unit tests, but the live API contract (authentication, field names, status enum values in production) can only be confirmed with real credentials. This is the only manual-only verification identified in `08-VALIDATION.md`.

---

## Gaps Summary

No automated gaps. All 4 success criteria are fully met by the implemented code. The only open item is the single manual live-API smoke test that cannot be performed without Zefix credentials, which must be obtained externally.

---

_Verified: 2026-06-15_
_Verifier: Claude (gsd-verifier)_
