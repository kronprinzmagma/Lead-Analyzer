---
phase: 04-zahlungskraeftigkeit-estimator
verified: 2026-06-14T00:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
gaps: []
---

# Phase 4: Zahlungskräftigkeit Estimator Verification Report

**Phase Goal:** Each customer gets a documented 1-5 Zahlungskräftigkeit estimate from public signals, clearly labelled as an estimate.
**Verified:** 2026-06-14
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each row gets a 1-5 estimate combining legal form (word-bounded AG/GmbH/Einzelfirma), branch kaufkraft tier, and website size signals (AC5) | ✓ VERIFIED | `payment.py:39-47` `_LEGAL` `\b`-anchored table (AG/SA/KlG case-sensitive); `:70-95` `_branch_tier` tier map; `:102-123` `_size_signals` team/jobs/standorte each +1 cap≤2; combined in `estimate()` `:148-157`. Not stubbed. Live run distribution `[1×3, 2×9, 3×8, 4×7, 5×13]` over 42 rows. |
| 2 | Every estimate labelled as estimate with driving signals recorded; thin data → conservative score, no invented facts (AC5, AC6) | ✓ VERIFIED | All 42 output rows carry `"Zahl (Schätzung):"` (live run: 42/42 labelled). `models.py:32-41` `PaymentEstimate.signals`. Conservative default `payment.py:154-156`: `resolved` predicate → 2 + "dünne Datenlage" only on truly thin data (incl. unknown non-empty Branche, `test_conservative_default_unknown_branche`). Zero "CHF"/"Umsatz" in any begründung (live: 0). |
| 3 | Score direction correct: higher = more purchasing power (AC3) | ✓ VERIFIED | Direction sweep: AG+Zahnarzt+rich=5 ≥ AG+Zahnarzt=5 ≥ GmbH+Maler=3 ≥ Einzelfirma+Bäckerei=1; thin/unknown=2. Monotonic. `_map_to_1_5` `:130-133` clamps to int [1,5]. `test_direction_monotone`, `test_zahl_range` pass. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lead_analyzer/analyzers/payment.py` | estimate() legal form + branch tier + size → 1-5, conservative default | ✓ VERIFIED | 159 lines, full A/B/C logic + resolved-predicate default. No TODO/placeholder. |
| `lead_analyzer/models.py` PaymentEstimate | dataclass zahl/reason/signals | ✓ VERIFIED | `:31-41`, reason always "Zahl (Schätzung): " prefixed. |
| `lead_analyzer/reasons.py` | per-section cap, carries both bedarf+zahl rationale | ✓ VERIFIED | `:30-58` per-section cap 160 (not global 200) so zahl reason never truncated; `test_payment_section_not_truncated` passes. |
| `lead_analyzer/pipeline.py` | analyze_row real zahl on all 3 paths | ✓ VERIFIED | normal `:60`, empty-URL `:41`, exception-boundary `:68`; double-guarded fallback `:71`. |
| `tests/test_payment.py` | full matrix A/B/C/combine/default/misfire/direction/range | ✓ VERIFIED | 13 tests pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| pipeline.analyze_row | payment.estimate | call on all 3 paths | ✓ WIRED | `:60,:41,:68` — real call, result flows to RowResult.zahl + reason. |
| pipeline | reasons.build(payment=est) | begründung column | ✓ WIRED | `:63` passes payment; output column "Begründung" carries both rationale (live verified). |
| reasons.build | PaymentEstimate.reason | per-section cap | ✓ WIRED | `:57-58`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `pytest tests/ -q` | 154 passed in 0.15s | ✓ PASS |
| Offline robustness (all rows forced-unreachable) | custom script, fetch→unreachable | 42 rows, 0 bad, both scores int 1-5, no crash | ✓ PASS |
| Live best-effort full run | `run.py data/sample_input.xlsx -o output/phase4_verify.xlsx` | 42 rows, exit 0, all zahl int 1-5, 42/42 labelled, 0 invented facts | ✓ PASS |
| Legal-form misfires | direct `_legal_form` calls | Magazin GmbH→GmbH(1), Sagi/Casa/Sava/Marco→0, Krauer-Sommer AG→AG(2) | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| ZK-01 | estimate from legal form + branch tier + size signals | ✓ SATISFIED | payment.py A/B/C; Truth 1 |
| ZK-02 | labelled estimate, signals recorded, no invented facts | ✓ SATISFIED | "Zahl (Schätzung):" 42/42; signals list; 0 CHF; Truth 2 |
| ZK-03 | higher = more purchasing power | ✓ SATISFIED | monotonic sweep; Truth 3 |
| NACH-01 | begründung carries both rationale, zahl not truncated | ✓ SATISFIED | per-section cap; test_payment_section_not_truncated; live begründung shows "… → Bedarf N | Zahl (Schätzung): …" |

### Anti-Patterns Found

None. No TODO/FIXME/placeholder/"not implemented" in payment.py or reasons.py. No stale `zahl==3 placeholder` assertion remains (grep confirmed; old placeholder replaced by `>=4`/real-estimate assertions in test_pipeline_bedarf.py:184,204 and test_pipeline_dim1.py:84,165).

### Regression Check

Bedarf (Phase 3) untouched: `reasons.build(verdicts)` with `payment=None` is byte-for-byte unchanged (`test_build_without_payment_unchanged`); scoring.bedarf logic unchanged in pipeline `:59`. All 154 tests green.

### Calibration Concerns for Phase 7 (informational, non-blocking)

1. **Branch tier list is a closed allowlist** (`_TIER` ~14 keys). Any branch not in the list → "Branche unbekannt" → tier 0. On the live sample this is acceptable (conservative, flagged), but Phase 7's full-rationale pass may want to widen/audit the tier map or expose the DIFF-03 config override.
2. **Size signals rely on href/anchor-text regex** (`/team`, `/jobs`, `/standorte`). German diacritic variants and JS-rendered nav are not captured; cap ≤2 keeps this a nudge, not a dominator — acceptable for the estimate's stated scope.
3. **Combine map maxes legal+tier+size = 2+2+2=6 → 5**; an AG alone (2) maps to 3, which is intentional but worth re-checking against real lead outcomes in Phase 7.

### Human Verification Required

None — all criteria verified programmatically against code and a live + offline run over the full 42-row sample.

### Gaps Summary

No gaps. All three ROADMAP success criteria and all four mapped requirements (ZK-01/02/03, NACH-01) are satisfied with code evidence, passing tests (154/154), an offline robustness run (42/42 rows scored, no crash), and a live full-sample run (42/42 labelled estimates, zero invented facts, both rationale present). AC2/AC3/AC5/AC6 verified.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
