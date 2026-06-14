---
phase: 04-zahlungskraeftigkeit-estimator
plan: 02
subsystem: scoring
tags: [tdd-green, zahlungskraeftigkeit, estimator]
requires: [PaymentEstimate, test_payment.py]
provides: [payment.estimate, payment._legal_form, payment._branch_tier, payment._size_signals, payment._map_to_1_5]
affects: [lead_analyzer/analyzers/payment.py]
tech-stack:
  added: []
  patterns: [pure-offline-analyzer, word-bounded-case-sensitive-regex, soup-none-neutral-guard]
key-files:
  created: [lead_analyzer/analyzers/payment.py]
  modified: []
decisions:
  - "AG/SA/KlG matched \\b-anchored + case-sensitive (no re.I); GmbH/Sàrl/Einzelfirma re.I"
  - "resolved predicate is the single source of truth; no `if not notes:` shortcut"
  - "Group C capped ≤2 so it nudges but never dominates; soup=None → neutral (0,[])"
  - "Reuses scoring.clamp_score; no hand-rolled clamp; no new dependency, no Zefix/LLM"
metrics:
  duration: ~4min
  completed: 2026-06-14
---

# Phase 4 Plan 02: Zahlungskräftigkeit Estimator (GREEN) Summary

Pure offline Zahlungskräftigkeit estimator built from three public signal groups (legal form
from name + branch tier + website size signals), each point traced to a named signal or
labelled assumption (AC5/AC6). All 13 Plan-01 tests now pass GREEN.

## What was built

- `lead_analyzer/analyzers/payment.py` (158 lines): `_legal_form` (group A, ordered \b-anchored
  table, AG/SA/KlG case-sensitive), `_branch_tier` (group B, transparent tier dict, unknown →
  sole "Branche unbekannt"), `_size_signals` (group C, soup-None neutral guard, cap ≤2),
  `_map_to_1_5` (combine via clamp_score), `estimate` (orchestration + verbatim resolved
  predicate → conservative 2 + "dünne Datenlage").

## Verification

- `python -m pytest tests/test_payment.py` → 13 passed (GREEN).
- Full suite → 148 passed (135 prior + 13; payment.py standalone, no wiring yet).
- grep gates: clamp_score×2 (≥1); AG regex line has no re.I; "Zahl (Schätzung):"×2 (≥2);
  "Branche unbekannt"×9 (≥2); 158 lines (≥80).

## Threat Mitigations Applied

- T-04-01 (ReDoS): only \b-anchored simple alternations, no nested quantifiers.
- T-04-02 (info disclosure): reason lists labelled signals only; no CHF/Umsatz figures.
- T-04-03 (legal-form misfire): word-bounded + case-sensitive AG/SA/KlG; misfire tests green.

## Deviations from Plan

None - plan executed exactly as written. Implemented as one file rather than two split
RED-driven commits, since the module is a single cohesive unit; A/B subset verified green
before the full-suite check.

## Self-Check: PASSED
- payment.py exists; estimate/helpers importable; all tests green; commit present.
