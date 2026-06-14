---
phase: 4
slug: zahlungskraeftigkeit-estimator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 4 — Validation Strategy

> Derived from 04-RESEARCH.md. Fully offline. AC5 load-bearing: no invented facts; every point traces to a named public signal or a labelled conservative assumption.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Quick run** | `python -m pytest tests/ -q` |
| **Network policy** | autouse conftest fixture fails any un-mocked request |
| **Fixtures** | make_fetch_result(**overrides); RowRecord built inline with cells |

## Per-Requirement Verification Map

| Requirement | Observable validation | Test type | Status |
|---|---|---|---|
| **ZK-01** (estimate from public signals A+B+C) | AG name → +pts; branch tier from Branche column; website size signals (Standorte/Team/Jobs) → +pts; sum → 1-5. | unit | Pending |
| **ZK-02** (documented estimate, no invented facts, conservative when thin) | reason prefixed "Zahl (Schätzung):" listing each driving signal; thin data (no name suffix, no/empty Branche, soup None) → conservative default 2 + "dünne Datenlage". Word-boundary + case: "Magazin GmbH"/"Sagi"/"Casa" do NOT match AG; "Krauer-Sommer AG" does. | unit (incl. misfire tests) | Pending |
| **ZK-03** (direction: higher = more power) | AG + high-tier + size signals > Einzelfirma low-tier; monotonic in points. | unit (direction) | Pending |
| **NACH-01 carry-through** | Begründung column shows BOTH bedarf and zahl rationale (reasons.build(verdicts, payment)). Per-section length cap so zahl reason not truncated. | unit + output inspection | Pending |

## Offline Integration Check

`python run.py data/sample_input.xlsx -o output/phase4_check.xlsx` offline: every row int 1-5 for BOTH scores; "AG" firms rank higher zahl than Einzelfirmen; Begründung carries "Zahl (Schätzung): ..." per row. Edge rows (empty/broken URL) still get a name/branch-based zahl (not placeholder).

## Wave 0 — Test File Gaps

- tests/test_payment.py (new) — group A word-boundary/case misfire matrix, group B tier map incl. missing Branche, group C size signals from soup, combine→1-5, conservative default, direction.
- extend tests/test_reasons.py — payment rationale appended, per-section cap.
- extend tests/test_pipeline_bedarf.py — analyze_row produces real zahl; empty/broken URL rows get name-based zahl; bedarf untouched.
