---
phase: 07-hardening-readme-full-sample-run
plan: 02
subsystem: docs
tags: [ac10, rationale, sample-run, scoring, verification]

requires:
  - phase: 06-optional-pagespeed-rate-limiting
    provides: complete Dim-1..6 scoring pipeline wired into analyze_row
provides:
  - "AC10 written rationale (docs/sample_run_rationale.md) over the full 42-row sample"
  - "Documented score distributions, edge-case justification, Gross-vs-klein contrast"
affects: [readme, verification]

tech-stack:
  added: []
  patterns: ["Rationale doc grounded in a reproducible offline run with verbatim Begründung strings"]

key-files:
  created: [docs/sample_run_rationale.md]
  modified: []

key-decisions:
  - "Live 42-row run distributions matched the plan <facts> exactly — used verbatim, no fabrication"
  - "Pulled real Begründung strings from the re-run to ground every cited example"

patterns-established:
  - "AC-justification docs cite real output values, not assumed ones"

requirements-completed: [SETUP-02]

duration: 6min
completed: 2026-06-14
---

# Phase 7 Plan 02: Sample-Run-Begründung (AC10) Summary

**docs/sample_run_rationale.md: AC10 justification over the full 42-row sample — confirmed Bedarf {1:3,2:12,3:15,4:10,5:2} / Zahl {1:3,2:9,3:10,4:7,5:13}, both Bedarf-5 edge cases, and the AG/Treuhand-vs-Coiffeur kaufkraft contrast.**

## Performance

- **Duration:** ~6 min
- **Tasks:** 2 (both write the single doc; committed as one atomic docs commit per the docs-only plan)
- **Files modified:** 1

## Accomplishments
- Reproduced the full run (`python run.py data/sample_input.xlsx -o output/sample_rationale.xlsx`) — 42 rows, offline, no PSI key.
- Confirmed live distributions match the plan facts exactly (no deviation).
- Documented both edge cases (Kiosk leere URL → B5/Z1; Nähatelier kaputte `htp://` → B5/Z2) with the "keine Website überschreibt auf 5" rule and AC4 robustness (no crash).
- Contrasted high-Zahl AG/GmbH/Treuhand leads (KMU Treuhandexperte GmbH B4/Z5, Lippuner AG B4/Z5) against the low-Zahl Coiffure Heidi (B1/Z1), plus the "kein Bedarf" cluster (ONE! Treuhand B1/Z4).
- Explained how to read the Begründung column and flagged the Dim-3 viewport-heuristic fallback (no PSI key) + AC5 Schätzung labelling, citing verbatim Begründung strings.

## Task Commits

1. **Task 1 + Task 2: full run + rationale doc** - `b46a2f0` (docs)

**Plan metadata:** (this SUMMARY + STATE/ROADMAP) — separate metadata commit.

## Files Created/Modified
- `docs/sample_run_rationale.md` - AC10 rationale: ## Lauf (reproducible command, 42 rows, offline), ## Verteilung (both distribution tables), ## Edge-Cases, ## Gross vs. klein, ## Begründung-Spalte reading guide.

## Decisions Made
- Live distributions matched plan `<facts>` verbatim — cited directly, nothing fabricated.
- Used real Begründung strings extracted via openpyxl to ground each cited example.

## Deviations from Plan
None - plan executed exactly as written. Output file written to `output/sample_rationale.xlsx` (gitignored, not committed) as instructed.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- AC10 written justification complete and auditable. README plan (07-01) and verification (07-05) can reference this doc.

## Self-Check: PASSED
- `docs/sample_run_rationale.md` exists (FOUND)
- Commit `b46a2f0` exists (FOUND)
- All Task 1 + Task 2 verification greps pass (Kiosk, Nähatelier, Coiffure Heidi, Treuhandexperte/Lippuner, 15, 13, 42, command)

---
*Phase: 07-hardening-readme-full-sample-run*
*Completed: 2026-06-14*
