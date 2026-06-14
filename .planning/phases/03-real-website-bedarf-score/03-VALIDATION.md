---
phase: 3
slug: real-website-bedarf-score-dims-2-4-5-6-aggregation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 3 — Validation Strategy

> Derived from 03-RESEARCH.md "## Validation Architecture". Tool + tests fully offline (mock requests; NO PSL download — tldextract rejected).

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Quick run** | `python -m pytest tests/ -q` |
| **Network policy** | autouse conftest fixture fails any un-mocked request |
| **Fixtures** | `make_fetch_result(**overrides)` builds FetchResult variants offline |

## Per-Requirement Verification Map

| Requirement | Observable validation | Test type | Status |
|---|---|---|---|
| **BED-02** (Technische Basis) | http-only → gap/severe; free subdomain (host.endswith builder) → severe; ssl_ok=False → severe; own https domain → ok. `evilwix.com` must NOT match `wix.com`. | unit (mocked FetchResult) | Pending |
| **BED-04** (SEO) | missing title → gap; missing meta desc → gap; 0 or >1 h1 → gap; `<meta robots noindex>` OR `X-Robots-Tag: noindex` header → severe; good page → ok. | unit | Pending |
| **BED-05** (KI-Readiness) | JSON-LD + OG present → ok; some OG no JSON-LD → gap; nothing structured → severe. | unit | Pending |
| **BED-06** (Inhalt/Aktualität) | no contact form & no tel/mailto & no Impressum → gap/severe; stale copyright year (≥4y) → severe; legacy generator → gap; fresh complete page → ok. | unit | Pending |
| **BED-07** (Aggregation) | gap-points G + severe-count S → bands exactly per docs/scoring_website_bedarf.md; dead → 5 override non-bypassable; tie-break takes higher. | unit (table-driven) | Pending |
| **BED-08** (Monotonic direction) | modern site over all dims → 1; broken/empty → 5; adding gaps never lowers Bedarf (gradient test). | unit (direction) | Pending |
| **NACH-01** (Traceability) | RowResult.reason lists each dimension's verdict + driving signal; appears in output Begründung column. | unit + output inspection | Pending |

## Offline Integration Check

`python run.py data/sample_input.xlsx -o output/phase3_check.xlsx` completes offline; every row int 1-5; edge rows → 5; Begründung column populated per row with dimension breakdown.

## Wave 0 — Test File Gaps

- tests/test_technical.py, test_seo.py, test_ai_readiness.py, test_content.py — per-dimension verdict matrices.
- tests/test_scoring_bedarf.py — table-driven aggregation + override + monotonic direction tests.
- tests/test_reasons.py — reason-string format.
- extend tests/test_pipeline_dim1.py → full-pipeline offline reason + integration.
