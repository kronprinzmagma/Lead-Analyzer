---
phase: 2
slug: fetch-existence-dim-1-robustness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract. Derived from 02-RESEARCH.md "## Validation Architecture".
> Hard constraint: tool AND test suite must run with NO network (mock requests).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none (pytest auto-discovers tests/) |
| **Quick run command** | `python -m pytest tests/ -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~1 second |
| **Network policy** | autouse conftest fixture fails any unmocked real `requests` call |

---

## Sampling Rate

- **After every task commit:** `python -m pytest tests/ -q`
- **Before verify-work:** full suite green
- **Max feedback latency:** ~2 seconds

---

## Per-Requirement Verification Map

| Requirement | Observable validation | Test type | Status |
|---|---|---|---|
| **BED-01** (Dim 1 really measured) | reachable site → ok verdict; parked markers → dead; social host → severe-with-presence; thin content → gap. Unit tests with mocked `FetchResult`. | unit (mocked) | Pending |
| **ROB-01** (edge cases never crash, sensible score) | empty URL (Kiosk) → Bedarf 5 no fetch; `htp://naehatelier-sutter` → "nicht erreichbar" → Bedarf 5; timeout/refused → Bedarf 5; all without exception. | unit (mocked) + offline integration on sample rows 41–42 | Pending |
| **ROB-02** (fetch hardening) | fetch uses timeout tuple, browser UA + de-CH, redirect cap, size cap, encoding fallback; SSLError → `ssl_ok=False` not crash; 403/429 → "blockiert" neutral score (NOT 5). | unit (mocked responses/exceptions) | Pending |
| **ROB-03** (per-row exception boundary) | an analyzer that raises is caught; row still gets a scored RowResult with an error note; run completes. Test injects a raising analyzer. | unit (mocked) | Pending |

## Offline Integration Check

`python run.py data/sample_input.xlsx -o output/phase2_check.xlsx` over all 42 rows completes without network access required for a non-crashing result, edge rows 41/42 score Bedarf 5. (With network, reachable sites get real verdicts.)

## Wave 0 — Test File Gaps

- `tests/test_fetch.py` — normalize() variant order, exception→note map, SSL-as-signal, size cap (mocked).
- `tests/test_existence.py` — verdict mapping for reachable/parked/social/thin/dead.
- `tests/conftest.py` — autouse fixture blocking un-mocked network.
- Extend `tests/` for analyze_row override (dead → Bedarf 5) and per-row exception boundary.
