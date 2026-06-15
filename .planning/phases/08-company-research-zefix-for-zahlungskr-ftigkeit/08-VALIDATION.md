---
phase: 8
slug: company-research-zefix-for-zahlungskr-ftigkeit
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-15
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 08-RESEARCH.md "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | existing (pytest discovers `tests/`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_zefix_client.py tests/test_payment.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest -x -q` |
| **Estimated runtime** | ~1 second (offline; all network monkeypatched) |

---

## Sampling Rate

- **After every task commit:** Run quick command (`test_zefix_client.py` + `test_payment.py`)
- **After every plan wave:** Run full suite (currently 206 tests — must stay green)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DIFF-01 | from_config returns None without creds → offline-identical | unit | `pytest tests/test_zefix_client.py::test_unavailable_without_creds -x` | ❌ W0 |
| DIFF-01 | POST search 200 + exactly 1 result → CompanyFacts parsed | unit | `pytest tests/test_zefix_client.py::test_single_match_parsed -x` | ❌ W0 |
| DIFF-01 | 0 results → None (negative cached) | unit | `pytest tests/test_zefix_client.py::test_zero_results_none -x` | ❌ W0 |
| DIFF-01 | >1 results → None (ambiguous, negative cached) | unit | `pytest tests/test_zefix_client.py::test_ambiguous_none -x` | ❌ W0 |
| DIFF-01 | Timeout → None, no raise | unit | `pytest tests/test_zefix_client.py::test_timeout_none -x` | ❌ W0 |
| DIFF-01 | 429 → retry with injected sleep, then None | unit | `pytest tests/test_zefix_client.py::test_429_retry_capped -x` | ❌ W0 |
| DIFF-01 | Budget=0 → None without network call | unit | `pytest tests/test_zefix_client.py::test_budget_exhausted -x` | ❌ W0 |
| DIFF-01 | Cache hit → return without network and without budget | unit | `pytest tests/test_zefix_client.py::test_cache_hit_no_network -x` | ❌ W0 |
| DIFF-01 | Negative cache hit (`_miss`) → None without network | unit | `pytest tests/test_zefix_client.py::test_negative_cache_hit -x` | ❌ W0 |
| DIFF-01 | Short name (<3 chars) → None without network call | unit | `pytest tests/test_zefix_client.py::test_short_name_guard -x` | ❌ W0 |
| ZK-01/NACH-01 | estimate with facts AG ACTIVE → zahl boosted, signal logged | unit | `pytest tests/test_payment.py::test_zefix_ag_active -x` | ❌ W0 |
| ZK-01/NACH-01 | estimate with facts GmbH CANCELLED → penalty applied, signal logged | unit | `pytest tests/test_payment.py::test_zefix_gmbh_cancelled -x` | ❌ W0 |
| DIFF-01 | estimate facts=None → byte-identical to existing offline baseline | unit | `pytest tests/test_payment.py::test_zefix_none_fallback -x` | ❌ W0 |
| PERF-02 | Full run without creds → no ZefixClient created, no network | integration | `pytest tests/test_pipeline_dim1.py -x` (existing, must still pass) | ✅ |

*Status: ❌ W0 = test does not exist yet, created in Wave 0 · ✅ = covered by existing infrastructure*

---

## Wave 0 Requirements

- [ ] `tests/test_zefix_client.py` — all ZefixClient unit tests (mirrors `tests/test_pagespeed_client.py`)
- [ ] Additional test functions in `tests/test_payment.py` — `zefix_facts` scenarios (AG ACTIVE boost, GmbH CANCELLED penalty, None → baseline)

*Existing `tests/conftest.py` network-block + `FakeResponse` fixtures are reused; no new framework install.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real authenticated Zefix lookup returns expected legal form/status for a known firm | DIFF-01 | Needs live creds + network; not run in offline CI | With `ZEFIX_USER`/`ZEFIX_PASSWORD` in `.env`, run the tool over a few sample rows and confirm the run-log shows `confidence: zefix` with a plausible `legal_form`/`status` and a valid `source_url`. |

---

*Phase: 08-company-research-zefix-for-zahlungskr-ftigkeit*
*Validation strategy derived 2026-06-15 from 08-RESEARCH.md*
