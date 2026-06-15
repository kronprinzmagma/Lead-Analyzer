---
phase: 08-company-research-zefix-for-zahlungskr-ftigkeit
plan: "02"
subsystem: payment-scoring + pipeline-wiring
tags: [zefix, payment-scoring, pipeline-wiring, run-log, tdd]
dependency_graph:
  requires: [lead_analyzer/clients/zefix.py, lead_analyzer/models.py ZefixFacts, plan 08-01]
  provides: [authoritative Group A legal-form scoring, status modifier, Zefix wiring in pipeline]
  affects: [lead_analyzer/analyzers/payment.py, lead_analyzer/pipeline.py, tests/test_payment.py]
tech_stack:
  added: []
  patterns:
    - "zefix_facts=None trailing kwarg for backward-compatible byte-identity"
    - "_zefix_facts() closure in analyze_row for safe lookup on normal/empty-url paths"
    - "Post-aggregation status modifier clamped with scoring.clamp_score"
key_files:
  created: []
  modified:
    - lead_analyzer/analyzers/payment.py
    - lead_analyzer/pipeline.py
    - tests/test_payment.py
decisions:
  - "zefix_facts=None as trailing keyword arg preserves byte-identity for all existing callers — no migration needed"
  - "_zefix_facts() defined as closure inside analyze_row — avoids threading record/zx_client through a module-level helper"
  - "Exception path in analyze_row does NOT call Zefix — minimal error boundary per T-08-08 (lookup never raises but outer boundary stays clean)"
  - "Empty-URL path DOES call Zefix — no network needed for the name-based lookup; Zefix improves score even without a website"
  - "resolved predicate gains zefix_facts is not None as first OR term — Zefix hit always resolves (authoritative signal)"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_changed: 3
---

# Phase 8 Plan 02: Zefix Scoring Wiring Summary

**One-liner:** payment.estimate() gains zefix_facts=None kwarg routing authoritative legal form through _legal_form_from_zefix + _status_modifier; ZefixClient built once in run() and threaded through analyze_row — 3 new tests, 219 total green, byte-identical without creds.

## What Was Built

### Task 1 — RED tests (commit fef1e88)

- `ZefixFacts` imported into `tests/test_payment.py`
- `_facts()` helper returning a minimal `ZefixFacts` fixture
- Three new test functions (names binding per 08-VALIDATION.md):
  - `test_zefix_ag_active` — AG from Zefix (name has no AG token) → zahl=5, signal contains "Zefix", "autoritativ", uid
  - `test_zefix_gmbh_cancelled` — GmbH CANCELLED → pre-penalty=4, -2 penalty, zahl=2, signal mentions "Status" + "gelöscht"
  - `test_zefix_none_fallback` — zefix_facts=None field-by-field equals offline baseline (LOAD-BEARING byte-identity guard)
- Suite RED: TypeError on `zefix_facts` unexpected keyword arg (intended)

### Task 2 — GREEN payment.py (commit 5b70211)

- `ZefixFacts` imported into `lead_analyzer/analyzers/payment.py`
- `_legal_form_from_zefix(facts: ZefixFacts)` added after `_legal_form()` (fallback preserved unchanged):
  - Maps `legal_form_de` to same point table as `_LEGAL` (AG/SA=2, GmbH/Sàrl/Sarl/KlG/&Co=1, Einzelunternehmen=0, unknown=0)
  - Signal note: `"Rechtsform {label} aus Zefix (autoritativ, Quelle: {uid})"`
- `_status_modifier(facts)` added:
  - ACTIVE → 0 (no change)
  - BEING_CANCELLED → -1, signal `"Status: in Liquidation (Zefix, {source_url})"`
  - CANCELLED → -2, signal `"Status: gelöscht (Zefix, {source_url})"`
- `estimate()` signature → `estimate(record, fr, soup, config, zefix_facts=None)`:
  - Group A branches on `zefix_facts is not None`: authoritative path vs name heuristic
  - `resolved` predicate gains `zefix_facts is not None` as first OR term
  - Post-aggregation: `zahl = scoring.clamp_score(_map_to_1_5(pa+pb+pc) + penalty)`
  - Status penalty notes appended to signals → flow into RowResult.zahl_signals → JSONL run-log (NACH-01)
- All 24 payment tests green (was 21)

### Task 3 — WIRE pipeline.py (commit e686d70)

- `from .clients.zefix import ZefixClient` added to imports
- `analyze_row` signature: `def analyze_row(record, url_col, config, ps_client=None, zx_client=None)`
- `_zefix_facts()` closure inside `analyze_row`:
  - Guards `zx_client is None or not zx_client.is_available()` → None
  - Reads `Kundenname` and optional `Kanton` cell; calls `zx_client.lookup()`
- Normal path: `zefix_facts = _zefix_facts()` then `payment.estimate(..., zefix_facts=zefix_facts)`
- Empty-URL path: same lookup (name-based, no network needed)
- Exception path: no Zefix call (minimal boundary per T-08-08)
- `run()`: `zx_client = ZefixClient.from_config(config)` immediately after `ps_client = PageSpeedClient.from_config(config)`
- `pool.submit(analyze_row, r, url_col, config, ps_client, zx_client)` — both clients passed positionally
- Without creds: `from_config` → None → `_zefix_facts()` → None → `zefix_facts=None` → byte-identical to Phase 7

## Test Results

```
Task 1 RED: 3 failed (TypeError — intended)
Task 2 GREEN: 24 passed (tests/test_payment.py)
Task 3 full suite: 219 passed (was 216 after 08-01)
```

## Decisions Made

1. **zefix_facts=None trailing keyword arg** — all existing `estimate()` callers are positional `(record, fr, soup, config)` so the trailing kwarg adds zero migration burden. Byte-identity guaranteed by `test_zefix_none_fallback`.
2. **_zefix_facts() closure** — defined inside `analyze_row` so it closes over `record` and `zx_client` cleanly. Avoids a module-level helper that would need those values threaded in.
3. **Exception boundary stays Zefix-free** — `lookup()` never raises by contract (08-01), but the outer `except Exception` boundary must remain minimal to not mask new bugs. Decision: no change to the exception path.
4. **Empty-URL path DOES call Zefix** — the Zefix lookup is name-based only (no network/URL needed), so it can improve the `zahl` score even for rows with no website. This is correct per CLAUDE.md: Zahlungskräftigkeit from public sources regardless of website state.

## Deviations from Plan

None — plan executed exactly as written. All 3 task acceptance criteria grep checks pass. All must_haves verified.

## Threat Model Coverage

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-08-07 Tampering (name injection) | Raw cell → ZefixClient.lookup() → requests.post(json=body) auto-encodes | MITIGATED |
| T-08-08 DoS (lookup stalls row) | lookup() never raises (08-01 contract); not called on exception path | MITIGATED |
| T-08-09 Repudiation (unverifiable score) | source_url + uid + status in PaymentEstimate.signals → RowResult.zahl_signals → JSONL run-log | MITIGATED |
| T-08-10 Info Disclosure (creds in run-log) | Only uid, legal_form, status, source_url enter signals; ZEFIX_USER/ZEFIX_PASSWORD never reach payment.py | MITIGATED |
| T-08-11 Tampering (non-active scored as viable) | _status_modifier() penalizes CANCELLED(-2)/BEING_CANCELLED(-1) post-aggregation, clamped | MITIGATED |

## Known Stubs

None — authoritative legal form and status penalty are fully wired. The JSONL run-log already carries signals via the existing `RowResult.zahl_signals` channel. Capital/employees remain heuristic ("unknown") by design — requires a second GET /company/uid/{id} call, deferred per AC5 scope decision in 08-RESEARCH.md.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes beyond what was planned. ZefixClient (08-01) is the only new external dependency; this plan only wires it into the scoring layer.

## Self-Check: PASSED

- `lead_analyzer/analyzers/payment.py` exists: FOUND
- `lead_analyzer/pipeline.py` updated: FOUND
- `tests/test_payment.py` has 3 new zefix tests: FOUND (grep returns 3)
- `_legal_form_from_zefix` in payment.py: FOUND
- `_status_modifier` in payment.py: FOUND
- `estimate(zefix_facts=None)` signature: FOUND
- `ZefixClient.from_config` in pipeline.py: FOUND (1 occurrence)
- `from .clients.zefix import ZefixClient` in pipeline.py: FOUND
- commit `fef1e88` (RED): FOUND
- commit `5b70211` (GREEN): FOUND
- commit `e686d70` (WIRE): FOUND
- 219 tests passing: VERIFIED
- No ZEFIX_USER/ZEFIX_PASSWORD in payment.py or pipeline.py code: VERIFIED (only in comments)
