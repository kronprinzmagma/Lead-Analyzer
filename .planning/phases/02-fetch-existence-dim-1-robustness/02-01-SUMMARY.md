---
phase: 02-fetch-existence-dim-1-robustness
plan: 01
subsystem: fetch + existence (Dim 1) offline core
tags: [phase-2, dim-1, normalize, existence, test-infra, offline]
requires:
  - lead_analyzer.models (RowRecord, DimensionVerdict, RowResult)
  - pytest, requests, beautifulsoup4 (already installed)
provides:
  - lead_analyzer.models.FetchResult (raw-fetch carrier for Dim 1..6)
  - lead_analyzer.fetch.normalize() (pure URL variant builder)
  - lead_analyzer.analyzers.existence.analyze() (pure Dim-1 verdict)
  - tests/conftest.py (autouse network block + make_fetch_result/FakeResponse fakes)
affects:
  - plan 02-02 (fetch() wires against FetchResult + FakeResponse; analyze_row wires existence.analyze)
tech-stack:
  added: []
  patterns:
    - "Single network seam: only fetch.fetch() (02-02) touches the network; normalize + existence are pure/offline"
    - "Function-scoped autouse monkeypatch network block, per-test overridable (LIFO)"
key-files:
  created:
    - tests/conftest.py
    - lead_analyzer/fetch.py
    - lead_analyzer/analyzers/__init__.py
    - lead_analyzer/analyzers/existence.py
    - tests/test_fetch.py
    - tests/test_existence.py
  modified:
    - lead_analyzer/models.py
decisions:
  - "FetchResult added in Task 1 (not Task 2) because conftest imports it; clean prerequisite (Rule 3)"
  - "conftest helpers imported via `from conftest import ...` (tests dir on sys.path; no tests/__init__.py, matching Phase-1 style)"
metrics:
  tasks: 3
  files_created: 6
  files_modified: 1
  tests_total: 36
  tests_new: 21
  completed: 2026-06-14
---

# Phase 2 Plan 01: Fetch + Existence (Dim 1) Offline Core Summary

Built the pure, offline-testable foundation of Phase 2 — URL `normalize()`, the `FetchResult` carrier, the Dimension-1 `existence.analyze()` verdict, and an autouse conftest that blocks all real network in the test suite while exposing reusable fakes for plan 02-02. No network code ships here.

## What Was Built

- **`tests/conftest.py`** — function-scoped autouse fixture monkeypatching `requests.Session.get` and `requests.get` to raise `AssertionError("network used in tests")`. Per-test `monkeypatch.setattr(Session, "get", fake)` overrides it (LIFO). Module-level fakes: `make_fetch_result(**overrides)` and `FakeResponse` (with `.status_code/.url/.headers/.encoding/.apparent_encoding/.iter_content()`, encoding-fallback ready).
- **`lead_analyzer/models.FetchResult`** — dataclass carrier (url, ok, status, final_url, redirected, ssl_ok, headers, html, error). Phase-1 dataclasses untouched.
- **`lead_analyzer/fetch.normalize()`** — pure `normalize(raw) -> list[str] | None`. None/empty/whitespace -> None; strips malformed `htp://`-style schemes to bare host; ordered https/www/http variants with has_www guard; deduped order-preserving. No `fetch()` yet (02-02).
- **`lead_analyzer/analyzers/existence.analyze()`** — pure Dim-1 verdict over FetchResult, first-match priority: dead (error+no html), 403/406/429->gap "blockiert" (WAF guard, NOT Bedarf 5), 4xx/5xx no-body->severe, parked host/marker->severe, social host->severe, thin (<300 words)->gap, else ok. PARKED_HOSTS/PARKED_MARKERS/SOCIAL_HOSTS constants. bs4 html.parser, decompose script/style/nav/footer.

## Tests

36 passed (15 Phase-1 unchanged + 8 in test_fetch.py + 13 in test_existence.py). Network-block proven both ways: un-mocked `requests.get` raises; per-test monkeypatch override succeeds. 403/406/429 explicitly asserted as `gap` (not severe).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added FetchResult to models.py in Task 1 instead of Task 2**
- **Found during:** Task 1 — conftest.py imports `FetchResult`, so the Task-1 verify (suite must stay green) required the dataclass to exist already.
- **Fix:** Appended the `FetchResult` dataclass (exactly per `<interfaces>`/RESEARCH lines 434-448) during Task 1's commit. Task 2 then only added `normalize()` + tests.
- **Files modified:** lead_analyzer/models.py
- **Commit:** 41ba403

**2. [Rule 3 - Blocking] conftest helper import path**
- **Found during:** Task 3 — `from .conftest import make_fetch_result` failed (tests/ has no `__init__.py`, matching Phase-1 style; relative import has no parent package).
- **Fix:** Used `from conftest import make_fetch_result`. pytest puts the rootdir/test file dir on sys.path when no `__init__.py` is present, so the module resolves.
- **Files modified:** tests/test_existence.py
- **Commit:** 4f6d52c

## Authentication Gates

None.

## Known Stubs

None. `fetch()` (network) is intentionally deferred to plan 02-02 per the plan objective — not a stub, an explicit phase boundary. `existence.analyze()` and `normalize()` are fully implemented.

## Self-Check: PASSED

- All 7 artifact files FOUND.
- All 5 commit hashes present in git log (41ba403, 1705070, fe127a6, dab5a34, 4f6d52c).
- Full suite: 36 passed. `class FetchResult` count == 1. `def normalize` == 1, `def fetch` == 0. `def analyze` == 1.
