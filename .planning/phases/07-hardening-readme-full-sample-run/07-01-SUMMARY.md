---
phase: 07-hardening-readme-full-sample-run
plan: 01
subsystem: docs
tags: [readme, setup, ac9, setup-01]
requires: [run.py, lead_analyzer/cli.py, requirements.txt, .env.example, docs/scoring_website_bedarf.md]
provides: [README.md]
affects: []
tech-stack:
  added: []
  patterns: [graceful-degradation-documented]
key-files:
  created: [README.md]
  modified: []
decisions:
  - "README in German to match the project (German code comments, PO Nils)"
  - "Documented graceful degradation explicitly: tool runs fully without any API key"
metrics:
  duration: ~4min
  completed: 2026-06-14
---

# Phase 7 Plan 01: README.md (<5-min setup, AC9) Summary

Wrote the root `README.md` so a new user goes from clone to a scored `output/leads.xlsx`
in under 5 minutes with zero API keys (AC9 / SETUP-01), documenting graceful degradation,
all 8 CLI flags, both score mechanisms, the 6 Bedarf dimensions, caching/concurrency, privacy,
tests, and the real sample-run score distribution.

## What was done

**Task 1** (`1ebf033`) — README skeleton: title + one-paragraph "what it does" (Excel/CSV in →
same table + two integer scores + Begründung, sorted so ideal leads sit on top), Setup block
(venv + pip, Windows note), the one run command, a CLI-flags table covering every flag from
`lead_analyzer/cli.py` (`input`, `-o/--output`, `-n/--limit`, `--csv`, `--no-reason`, `--workers`,
`--no-cache`, `--no-pagespeed`), `.env`/API-keys section (all optional, `PAGESPEED_API_KEY` named,
OPENAI/ANTHROPIC reserved for deferred LLM layer), cache/re-run note, privacy note, pytest line.

**Task 2** (`c38a37f`) — "Wie die beiden Scores funktionieren": Website-Bedarf from the six named
dimensions (one line each) with the "no reachable website → 5" override and a link to
`docs/scoring_website_bedarf.md`; Zahlungskräftigkeit as a labelled estimate from legal form +
branch tier + website size signals; the `Begründung` column; plus a sample-run section citing the
real distribution (Bedarf {1:3,2:12,3:15,4:10,5:2}; Zahl {1:3,2:9,3:10,4:7,5:13}).

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- Task 1 automated grep check: OK (all 8 flag tokens + install/run/pytest/PAGESPEED present).
- Task 2 automated grep check: OK (both scores + rubric link + Schätzung present).
- Only `README.md` was created/modified; no other files touched (parallel-plan safe).

## Self-Check: PASSED

- FOUND: README.md
- FOUND commit: 1ebf033
- FOUND commit: c38a37f
