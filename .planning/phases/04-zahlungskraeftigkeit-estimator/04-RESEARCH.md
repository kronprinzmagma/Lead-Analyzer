# Phase 4: Zahlungskräftigkeit-Estimator - Research

**Researched:** 2026-06-14
**Domain:** Deterministic offline heuristic — estimate a 1–5 purchasing-power score per Swiss SME from public signals (legal form from name + branch tier + website size signals), fully labelled as an estimate.
**Confidence:** HIGH (architecture, code integration, test patterns are all grounded in existing Phase 1–3 code; the tier/point *values* are MEDIUM — estimates by design per AC5)

## Summary

Phase 4 replaces the `zahl` placeholder in `pipeline.analyze_row` with a real, deterministic, fully-offline estimator. Per the project's own upstream research (`FEATURES.md`, `ARCHITECTURE.md`), the estimator combines three signal groups: **(A)** legal form parsed word-bounded from `Kundenname`, **(B)** a branch purchasing-power tier looked up from the `Branche` column, and **(C)** factual website-size signals from the already-fetched HTML (`FetchResult.html` → the shared `soup`). It sums A+B+C and maps to 1–5, defaulting conservatively (2–3) with an explicit "dünne Datenlage" flag when nothing resolves. Every point traces to a named signal or a labelled assumption — the load-bearing AC5 constraint.

The architecture is already laid out: a new pure module `lead_analyzer/analyzers/payment.py` exposing `estimate(record, fr, soup, config) -> PaymentEstimate`, called from `analyze_row` right where `_zahl_placeholder` is today. The estimator returns an integer 1–5 plus a reason string; the reason is threaded into `RowResult.reason` alongside the existing bedarf reason. No network, no LLM, no Zefix in v1 (DIFF-01 deferred). The existing parse-once `soup` and `FetchResult` are reused — no new fetch.

**Primary recommendation:** Build `analyzers/payment.py` as a pure function `estimate(record, fr, soup, config)` returning a small `PaymentEstimate` dataclass (`zahl: int`, `reason: str`, `signals: list[str]`). Parse legal form with word-bounded regex (`\bAG\b`, `\bGmbH\b`, `\bSàrl\b`, `\bSA\b`, `\b& Co\b`, `\bKlG\b`, `\bEinzelfirma\b`), look up branch tier from a transparent dict, count factual HTML size signals from `soup`, sum, map to 1–5, clamp, and default to a conservative 2 with a "dünne Datenlage" note when no signal fires. Extend `reasons.build` to accept and append the payment reason so the `Begründung` column carries both bedarf and zahl rationale (NACH-01/AC6).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Legal-form parse from `Kundenname` | analyzer (`payment.py`) | — | Pure string logic over `RowRecord.cells`; no I/O |
| Branch-tier lookup from `Branche` | analyzer (`payment.py`) | config (DIFF-03 future) | Transparent dict; editable table is a future differentiator |
| Website size signals | analyzer (`payment.py`) | fetch (`FetchResult`/`soup`) | Reuses the one fetched page — no new HTTP (fetch-once-parse-many) |
| Combine A+B+C → 1–5 | analyzer (`payment.py`) | scoring (`clamp_score`) | Mapping + clamp; reuse `scoring.clamp_score` for the 1–5 guard |
| Thread estimate into output | pipeline + reasons | table_io | `analyze_row` wires it; `reasons.build` carries the text; `table_io` already writes `result.zahl` |

## User Constraints

> No CONTEXT.md exists for this phase (standalone research). Constraints are taken from CLAUDE.md (AC5/AC3/AC6), REQUIREMENTS.md (ZK-01/02/03, DIFF-01 deferred), and the phase objective.

### Locked Decisions (from objective + REQUIREMENTS + CLAUDE.md)
- Tool **and** tests fully offline. No external company-data API in v1. **Zefix deferred (DIFF-01).** No LLM in this phase.
- Pure deterministic heuristic from `RowRecord.cells` (`Kundenname`, `Branche`) + the per-row `FetchResult` HTML.
- **AC5 is load-bearing:** NO invented facts. Every point traces to a named public signal or a labelled conservative assumption. Conservative when data is thin, and say so.
- Keep Phase-3 bedarf logic untouched. Both scores integer 1–5, never empty (AC2/IO-04).

### Claude's Discretion
- Exact point values per legal form / branch tier / size signal (tune within the FEATURES.md ranges).
- Whether `PaymentEstimate` is a new dataclass or a `(int, str)` tuple (recommendation: dataclass, for log/traceability symmetry with `DimensionVerdict`).
- How the payment reason is concatenated into the `Begründung` column.

### Deferred Ideas (OUT OF SCOPE)
- DIFF-01 live Zefix lookup (upgrade name-assumption → confirmed fact). Note as optional future only.
- DIFF-02 LLM refinement of the estimate.
- DIFF-03 configurable branch→tier table (Sales-editable). Keep the dict transparent so this is a cheap future add.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ZK-01 | 1–5 score from public signals: legal form from name (AG/GmbH/Einzelfirma), branch tier, website size signals (Standorte/Team/Karriere) | Signal groups A/B/C below + combine map; word-bounded regex; bs4 detection on shared `soup` |
| ZK-02 | Estimate labelled as estimate; signals/assumptions traceable (Begründung and/or log); no invented facts; conservative + flagged when thin | `PaymentEstimate.reason` always prefixed "Zahl (Schätzung):"; conservative default with "dünne Datenlage"; `reasons.build` carries it into `Begründung` |
| ZK-03 | Score direction correct: higher = more purchasing power | Monotone sum→map (more/stronger signals only raise the score); direction regression test |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `re` (stdlib) | 3.x | Word-bounded legal-form matching | `\b…\b` anchors avoid the substring-misfire pitfall (Pitfall 16) `[VERIFIED: existing code uses re throughout]` |
| `beautifulsoup4` (bs4) | already installed (Phase 1–3 dep) | Parse `soup` for size signals (anchors, addresses, /team, /jobs) | Already the project HTML parser; reuse the shared parse-once `soup` `[VERIFIED: imported in pipeline.py, content.py, existence.py]` |

**No new dependencies.** This phase is pure stdlib + the already-present bs4. No `requests` call is added (Group C reads the already-fetched `soup`/`fr.html`).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Word-bounded `re` on the raw name | `tldextract`/NLP tokenizer | Overkill — Swiss legal-form suffixes are a small closed set; regex with `\b` and explicit Romandie/`& Co` handling is transparent (AC6) and ReDoS-free |
| Static dict branch table | Config-driven table (DIFF-03) | Deferred — keep the dict in `payment.py` but structured so a later config override is a one-liner |
| Zefix confirm | name-assumption only | Zefix deferred (DIFF-01); name-derived legal form stays a labelled *assumption*, fully offline |

## Architecture Patterns

### System Architecture Diagram

```
RowRecord.cells  ──Kundenname──►  [A] legal-form parse  (word-bounded re)  ──► points_A + "Rechtsform … angenommen (Quelle: Firmenname)"
              └───Branche─────►  [B] branch-tier lookup (dict)            ──► points_B + "Branchen-Tier (Annahme): …"
FetchResult/soup (already fetched) ─► [C] website size signals (bs4)       ──► points_C + factual notes ("3 Standorte", "/team", "/jobs")
                                                       │
                                          sum(A+B+C), cap
                                                       │
                              ┌────────────────────────┴────────────────────────┐
                              │  any signal fired?  ──► map sum→1–5 (clamp)       │
                              │  nothing fired?     ──► conservative 2 +          │
                              │                         "dünne Datenlage" flag    │
                              └────────────────────────┬────────────────────────┘
                                                       ▼
                              PaymentEstimate(zahl:int 1–5, reason:str, signals:list)
                                                       │
                  pipeline.analyze_row ──► RowResult(zahl=…, reason = bedarf-reason + zahl-reason)
                                                       │
                  reasons.build(verdicts, payment) ──► Begründung column (bedarf + zahl)
```

Data flow only; file mapping is in the Component table below. Note: **Group C never issues HTTP** — it consumes the `FetchResult` and shared `soup` that `analyze_row` already built (fetch-once-parse-many, ARCHITECTURE Anti-Pattern 2).

### Recommended Project Structure
```
lead_analyzer/
├── analyzers/
│   └── payment.py        # NEW: estimate(record, fr, soup, config) -> PaymentEstimate
├── models.py             # ADD: @dataclass PaymentEstimate (zahl, reason, signals)
├── pipeline.py           # EDIT: replace _zahl_placeholder(...) call with payment.estimate(...)
├── reasons.py            # EDIT: build(verdicts, payment=None) appends zahl reason
└── scoring.py            # REUSE: clamp_score() for the 1–5 guard
tests/
├── test_payment.py       # NEW: group A/B/C unit tests, misfire tests, conservative default
└── test_pipeline_bedarf.py / test_reasons.py  # EXTEND: zahl wired + Begründung carries both
```

### Pattern 1: Pure analyzer mirroring the Dim-analyzers
**What:** `payment.estimate` is a pure function — inputs in (`record`, `fr`, `soup`, `config`), `PaymentEstimate` out. Same shape as `content.analyze(fr, soup)`. No I/O, no globals, deterministic → trivially offline-testable.
**When to use:** Always here; matches the established analyzer contract and the "scoring/reasons are pure" rationale in ARCHITECTURE.
**Example:**
```python
# Source: pattern mirrors lead_analyzer/analyzers/content.py (existing code)
def estimate(record, fr, soup, config) -> PaymentEstimate:
    name = str(record.cells.get("Kundenname") or "")
    branche = str(record.cells.get("Branche") or "")
    pts_a, notes_a = _legal_form(name)      # group A
    pts_b, notes_b = _branch_tier(branche)  # group B
    pts_c, notes_c = _size_signals(soup)    # group C (factual; soup may be None)
    total = pts_a + pts_b + pts_c
    notes = notes_a + notes_b + notes_c
    if not notes:                            # nothing resolved → conservative + flagged
        return PaymentEstimate(2, "Zahl (Schätzung): dünne Datenlage, konservativ", [])
    zahl = _map_to_1_5(total)                # monotone; clamp to [1,5]
    return PaymentEstimate(zahl, "Zahl (Schätzung): " + "; ".join(notes), notes)
```

### Pattern 2: Word-bounded legal-form matching (the AC5/Pitfall-16 fix)
**What:** Match suffixes with `\b` anchors and case-insensitivity so `Krauer-Sommer AG` → AG but `Magazin GmbH` is not tripped by a substring `ag` inside `Magazin`. Each matched form yields points **and** an explicit "angenommen (Quelle: Firmenname)" note.
**When to use:** Group A, always.
**Example:**
```python
# Source: FEATURES.md group A + Pitfall 16 (word-bounded, not substring)
import re
# Order matters: check AG/SA (2 pts) before partnership/Einzelfirma.
_LEGAL = [
    (re.compile(r"\bAG\b"),                "AG",          2),  # Aktiengesellschaft
    (re.compile(r"\bSA\b"),                "SA",          2),  # Romandie AG
    (re.compile(r"\bGmbH\b", re.I),        "GmbH",        1),
    (re.compile(r"\bS(?:à|a)rl\b", re.I),  "Sàrl",        1),  # Romandie GmbH
    (re.compile(r"&\s*Co\b", re.I),        "& Co",        1),  # partnership (round 0.5→1 via int points)
    (re.compile(r"\bKlG\b"),               "KlG",         1),
    (re.compile(r"\bEinzelfirma\b", re.I), "Einzelfirma", 0),
]
```
> **Note on `\bAG\b` and case:** keep `AG`/`SA`/`KlG` **case-sensitive** (no `re.I`) — these are upper-case legal abbreviations. A lower-case `ag`/`sa` inside an ordinary word (e.g. "Sagi", "Magazin", "Casa") must NOT match. `\b` plus case-sensitivity is belt-and-suspenders against Pitfall 16. `GmbH`/`Sàrl`/`Einzelfirma` use `re.I` because they are full words unlikely to collide. `[CITED: PITFALLS.md Pitfall 16]`

### Pattern 3: Group C reads the shared `soup` (no new fetch), stays factual
**What:** Count concrete, page-present facts — multiple addresses/"Standorte", a team/Mitarbeiter page link, careers/Jobs link, fleet/Fuhrpark. Each is a *fact from the page* (AC5-safe), not an inference. `soup is None` (403/empty body) → zero points, note "keine Website-Signale (kein HTML)" — never penalise (mirrors the `content.py` soup-None guard).
**Example:**
```python
# Source: FEATURES.md group C; reuses the parse-once soup (ARCHITECTURE Anti-Pattern 2)
import re
def _size_signals(soup):
    if soup is None:
        return 0, []                      # not penalised, not invented
    pts, notes = 0, []
    hrefs = " ".join((a.get("href") or "") + " " + a.get_text(" ") for a in soup.find_all("a")).lower()
    if re.search(r"/team|/mitarbeiter|/ueber-uns|über uns", hrefs):
        pts += 1; notes.append("Team-/Über-uns-Seite")
    if re.search(r"/jobs|/karriere|offene stellen|stellenangebot", hrefs):
        pts += 1; notes.append("Karriere-/Jobs-Seite")
    if re.search(r"standorte|filialen", hrefs) or _multiple_addresses(soup):
        pts += 1; notes.append("mehrere Standorte")
    return pts, notes
```
> Keep these counts small and additive — Group C should *nudge*, not dominate. FEATURES.md assigns 0.5–1 each; with integer points cap the group's contribution (e.g. ≤2) so a content-rich micro-firm site can't out-score legal form + branch.

### Anti-Patterns to Avoid
- **Substring legal-form match (`"ag" in name`):** misfires on Sagi/Magazin/Casa. Use `\b` + case-sensitivity. (Pitfall 16)
- **Inventing facts for the reason:** never write a revenue/headcount number or a "Zefix says…" the tool didn't retrieve. Only state observed signals + labelled assumptions. (Pitfall 15 / AC5)
- **Letting Group C dominate:** a big marketing site for a sole proprietor shouldn't read as "wealthy". Cap Group C contribution.
- **Penalising thin data with a low score:** AC5 says conservative *middle-ish* (2–3) + flag, not 1. A 1 implies a confident "weak" verdict.
- **Re-fetching in `payment.py`:** reuse the `soup`/`fr` already built in `analyze_row`.
- **Reading `record.cells["Kundenname"]` assuming presence:** use `.get(...)` with empty-string fallback (Branche/Kundenname may be missing — see below).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 1–5 clamp/int guard | a new clamp | `scoring.clamp_score(value)` (existing) | Already tested, guarantees int in [1,5] (AC2) |
| HTML parse for Group C | a second `BeautifulSoup(...)` | the `soup` passed from `analyze_row` | parse-once-reuse (ARCHITECTURE Anti-Pattern 2) |
| Reason text plumbing | a parallel logging path | extend `reasons.build(verdicts, payment=...)` | One Begründung source of truth (NACH-01) |
| Test fetch fixtures | new fakes | `conftest.make_fetch_result(**overrides)` | Established offline fixture; net is blocked autouse |

**Key insight:** Phase 4 adds *zero* I/O and *zero* new dependencies. All the hard infrastructure (fetch, soup, clamp, output, net-block) exists; this phase is pure logic + wiring + tests.

## Answers to the Phase Questions

**Q1 — Legal form (group A).** Word-bounded regex, case-sensitive for upper-case abbreviations (`\bAG\b`, `\bSA\b`, `\bKlG\b`) and `re.I` for full words (`\bGmbH\b`, `\bSàrl\b`/`Sarl`, `\bEinzelfirma\b`), plus `&\s*Co\b`. Suggested integer points: AG/SA = 2, GmbH/Sàrl/& Co/KlG = 1, Einzelfirma/personal-name/no-suffix = 0. **Label every hit:** `"Rechtsform AG aus Firmenname angenommen (Quelle: Firmenname)"` — this is an assumption, not a fact, satisfying AC5. Special-case from PITFALLS: a personal name with a title (e.g. "Dr. med. dent. …" Zahnarzt) is an Einzelfirma but high-earner — Group B branch tier carries that, not Group A. `[CITED: FEATURES.md group A; PITFALLS.md Pitfall 16]`

**Q2 — Branch tier (group B).** Lookup against a transparent dict keyed by normalized (lower, trimmed) branch token, substring-tolerant since the `Branche` column holds free text:
- **High (+2):** Zahnarzt, Treuhand, Immobilien, Garage (Auto)
- **Medium (+1):** Schreinerei, Sanitär, Gartenbau, Handwerk, Maler, Confiserie
- **Lower (+0):** Bäckerei, Coiffeur, Velo, Floristik, Detailhandel

Label as `"Branchen-Tier (Annahme): Zahnarzt → hoch"`. **If `Branche` is missing/empty/unknown:** contribute 0 points and add note `"Branche unbekannt"`; do NOT guess. The conservative default catches the all-empty case. `[CITED: FEATURES.md group B; CLAUDE.md AC5]`

**Q3 — Website size signals (group C).** From the shared `soup`: team/über-uns link, careers/jobs link, multiple Standorte/filialen or multiple distinct addresses, optionally fleet/Fuhrpark for trade branches. Each +1 (cap group at ~2). All are page-present facts (AC5-safe). `soup is None` → 0 points + "kein HTML"-note, never a penalty. **Offline-testable** because it reads `soup`/`fr.html` only — build `soup` from an HTML string in the test (as `test_content.py` does). `[CITED: FEATURES.md group C; ARCHITECTURE fetch-once-parse-many]`

**Q4 — Combine A+B+C → 1–5.** Sum the three groups. Suggested map (monotone, AC3): `total ≥ 4 → 5`, `3 → 4`, `2 → 3`, `1 → 2`, `≤ 0 → 1`. **But:** the FEATURES.md `≤0 → 1` only applies when *some* signal fired and genuinely resolved low (e.g. Einzelfirma + lower branch). When **no** signal fires at all (no recognizable legal form, branch unknown, no HTML) → return a **conservative 2** with `"dünne Datenlage, konservativ geschätzt"` rather than a confident 1. Always pass through `scoring.clamp_score` to guarantee int∈[1,5]. Direction is monotone because every signal only adds non-negative points. `[CITED: FEATURES.md combine map; CLAUDE.md AC5 "konservativ schätzen und kennzeichnen"]`

**Q5 — Traceability (AC5/AC6/ZK-02).** Return `PaymentEstimate.reason`, always prefixed `"Zahl (Schätzung): "` so the estimate-nature is unmistakable. Thread it into the `Begründung` column by extending `reasons.build`:
```python
# reasons.build(verdicts, payment=None) -> str
def build(verdicts, payment=None) -> str:
    bedarf_text = _existing_bedarf_summary(verdicts)   # current behaviour, unchanged
    if payment is None:
        return bedarf_text
    return f"{bedarf_text} | {payment.reason}"          # both rationales, one cell
```
`analyze_row` passes `payment` to `reasons.build`. The full per-signal list also goes to the run-log (Phase 5/AC6) via `PaymentEstimate.signals`. The current `_MAX_LEN = 200` cap in `reasons.py` must be **raised or applied per-section** so the zahl reason isn't truncated away — recommend capping bedarf and zahl independently (e.g. 160 each) so both always appear. `[CITED: reasons.py current behaviour; NACH-01/AC6]`

**Q6 — Zefix stays OUT (DIFF-01).** Confirmed: REQUIREMENTS.md lists DIFF-01 (Live-Zefix-Lookup) under "v2 / Differentiators (deferred)" and Out-of-Scope forbids a Bonitäts-Audit. v1 is heuristic-only, fully offline. Document Zefix in `payment.py` as a future hook: the name-derived legal form is a labelled *assumption* that a later Zefix lookup could *upgrade* to a confirmed fact — but no code path calls it in v1. `[VERIFIED: REQUIREMENTS.md DIFF-01 deferred + Out of Scope]`

**Q7 — Validation Architecture:** see section below.

## Runtime State Inventory

Not applicable — Phase 4 is a greenfield code addition (new analyzer + wiring), not a rename/refactor/migration. No stored data, live-service config, OS-registered state, secrets, or build artifacts carry a renamed string. **None — verified: this phase adds `payment.py` and edits `pipeline.py`/`reasons.py`/`models.py` only.**

## Common Pitfalls

### Pitfall 1: Legal-form substring misfire
**What goes wrong:** `"ag" in name` flags "Magazin GmbH", "Sagi Bau", "Casa Bella" as AG.
**Why it happens:** naive substring matching.
**How to avoid:** `\bAG\b` case-sensitive (uppercase abbreviation) + a regression test asserting "Magazin GmbH" → GmbH only, "Sagi" → none.
**Warning signs:** every "...ag..." name scores high. `[CITED: PITFALLS.md Pitfall 16]`

### Pitfall 2: Hallucinated facts in the reason (AC5 violation)
**What goes wrong:** reason claims a revenue/headcount/founding-year or a source the tool never fetched.
**How to avoid:** reason only ever lists observed page signals + "(Quelle: Firmenname)"/"(Annahme)" labels. No numbers. Prefix "Zahl (Schätzung):".
**Warning signs:** specific figures, identical "sources" across rows, Zahl 5 for an obvious micro-firm. `[CITED: PITFALLS.md Pitfall 15]`

### Pitfall 3: Missing/empty `Kundenname` or `Branche` column
**What goes wrong:** `KeyError` or `None`-typed value crashes the estimator.
**How to avoid:** `str(record.cells.get("Kundenname") or "")`; unknown branch → 0 pts + "Branche unbekannt"; the per-row try/except in `analyze_row` is the final net but should not be the primary guard.
**Warning signs:** rows with blank branch crash or score oddly. `[VERIFIED: table_io reads cells as dict; sample has Kundenname/Branche but real lists may not]`

### Pitfall 4: `soup is None` penalised
**What goes wrong:** a 403/empty-body row gets Group C = penalty, inflating or deflating zahl wrongly.
**How to avoid:** soup-None guard returning 0 points + note (mirror `content.py`). zahl then rests on A+B (name+branch, which work offline regardless).
**Warning signs:** blocked sites get suspiciously low/high zahl. `[CITED: content.py soup-None guard]`

### Pitfall 5: Group C dominates
**What goes wrong:** a polished single-owner site out-scores an actual AG.
**How to avoid:** cap Group C contribution (≤2) and keep A (≤2) and B (≤2) as the spine.

## Code Examples

### PaymentEstimate dataclass (models.py)
```python
# Source: mirrors DimensionVerdict/RowResult in existing models.py
@dataclass
class PaymentEstimate:
    """Zahlungskräftigkeit-Schätzung (AC5: immer als Schätzung gekennzeichnet)."""
    zahl: int                 # 1..5, never empty (AC2/IO-04)
    reason: str               # "Zahl (Schätzung): …" — for Begründung + log
    signals: list[str] = field(default_factory=list)  # driving signals (AC6 log)
```

### Wiring in pipeline.analyze_row (replace `_zahl_placeholder`)
```python
# Source: current pipeline.py analyze_row, payment substituted for placeholder
from .analyzers import payment   # add to imports
...
soup = BeautifulSoup(fr.html, "html.parser") if fr.html else None
verdicts = [...]                                   # unchanged Phase-3 bedarf
bedarf = scoring.bedarf(verdicts)
est = payment.estimate(record, fr, soup, config)   # NEW — pure, offline
return RowResult(
    record.index, bedarf=bedarf, zahl=est.zahl,
    reason=reasons.build(verdicts, payment=est), verdicts=verdicts,
)
```
The two no-HTML early returns (empty URL, exception boundary) must **also** call `payment.estimate(record, None, None, config)` so even a "keine Website" row gets a real name/branch-based zahl (not the old placeholder 3). For the exception branch, wrap the estimate call defensively (fall back to conservative 2) so it can never re-raise inside the AC4 boundary.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `zahl = scoring.placeholder_result(record).zahl` (constant 3) | `payment.estimate(...)` real 1–5 | Phase 4 | `zahl` becomes meaningful; sort by (bedarf, zahl) finally ranks ideal leads |
| `reasons.build(verdicts)` (bedarf only) | `reasons.build(verdicts, payment=...)` (both) | Phase 4 | Begründung column carries bedarf + zahl rationale (NACH-01) |

**Deprecated/outdated after this phase:**
- `pipeline._zahl_placeholder` and the `zahl=3` path in `scoring.placeholder_result` — replaced by `payment.estimate`. Keep `placeholder_result` only if its Phase-1 tests still reference it; otherwise the bedarf side is already off it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Point values (AG=2, GmbH=1, branch High=2/Med=1, size +1 each, cap C≤2) | Q1–Q4 | Wrong *magnitudes* could mis-rank; direction stays correct (monotone). Tunable; AC5 only requires traceability, not precision |
| A2 | Branch tier assignments (Zahnarzt/Treuhand/Immobilien/Garage = high, etc.) | Q2 | Estimates by design (AC5); Sales can override (DIFF-03 future). Label as "(Annahme)" |
| A3 | Conservative default = 2 (not 3) when nothing resolves | Q4 | A 3 would over-rank empty-data rows above genuine low-power firms; 2 is the safer middle-low. Confirm with PO if desired |
| A4 | `Kundenname` and `Branche` are the exact column header strings | Q1–Q2 | Sample uses these verbatim `[VERIFIED: objective + sample columns]`; real lists may differ — use `.get` and degrade to conservative default if absent |

**These are estimates by design (AC5).** The *direction* (ZK-03) and *traceability* (ZK-02) are firm; the *values* are tunable and explicitly labelled assumptions.

## Open Questions

1. **`Begründung` length budget** — current `_MAX_LEN = 200` truncates. Recommendation: cap bedarf and zahl sections independently (~160 each) so both always survive. Decide in planning.
2. **Conservative default value (2 vs 3)** — A3 above. Recommendation: 2. Low risk either way; pick one and test it.
3. **Group C "multiple addresses" detection precision** — counting distinct addresses via regex is noisy. Recommendation: prefer explicit "/standorte"/"filialen" link/text signals over address-regex in v1; treat address-counting as optional refinement.

## Environment Availability

Skipped — Phase 4 has no external dependencies (pure offline code/logic change; no tools, services, or network).

## Validation Architecture

`nyquist_validation: true` in config — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing; 135 tests pass) |
| Config file | none detected (no pytest.ini/pyproject `[tool.pytest]`) — tests run from repo root; `conftest.py` provides autouse net-block + `make_fetch_result` |
| Quick run command | `python3 -m pytest tests/test_payment.py -x -q` |
| Full suite command | `python3 -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ZK-01 | AG name → higher points | unit | `python3 -m pytest tests/test_payment.py::test_legal_form_ag -x` | ❌ Wave 0 |
| ZK-01 | GmbH/Sàrl/Einzelfirma point mapping | unit | `pytest tests/test_payment.py::test_legal_form_variants -x` | ❌ Wave 0 |
| ZK-01 | Branch tier lookup (Zahnarzt high, Coiffeur low) | unit | `pytest tests/test_payment.py::test_branch_tiers -x` | ❌ Wave 0 |
| ZK-01 | Branche missing/empty → 0 pts + "unbekannt" | unit | `pytest tests/test_payment.py::test_branch_missing -x` | ❌ Wave 0 |
| ZK-01 | Group C size signals from soup (team/jobs/standorte) | unit | `pytest tests/test_payment.py::test_size_signals -x` | ❌ Wave 0 |
| ZK-01 | soup=None → Group C neutral (no penalty) | unit | `pytest tests/test_payment.py::test_size_signals_no_html -x` | ❌ Wave 0 |
| ZK-01 | combine A+B+C → 1–5 map | unit | `pytest tests/test_payment.py::test_combine_map -x` | ❌ Wave 0 |
| ZK-02 | reason prefixed "Zahl (Schätzung):" + lists signals | unit | `pytest tests/test_payment.py::test_reason_labelled -x` | ❌ Wave 0 |
| ZK-02 | nothing resolves → conservative 2 + "dünne Datenlage" | unit | `pytest tests/test_payment.py::test_conservative_default -x` | ❌ Wave 0 |
| ZK-02 | Begründung carries BOTH bedarf + zahl | integration | `pytest tests/test_reasons.py::test_build_with_payment -x` | ⚠️ extend existing |
| ZK-03 | direction monotone: stronger signals never lower zahl | unit | `pytest tests/test_payment.py::test_direction_monotone -x` | ❌ Wave 0 |
| (Pitfall 16) | "Magazin GmbH"→GmbH not AG; "Sagi"→none; "Casa"→none | unit | `pytest tests/test_payment.py::test_no_substring_misfire -x` | ❌ Wave 0 |
| (wiring) | analyze_row sets real zahl (not placeholder 3) incl. empty-URL row | integration | `pytest tests/test_pipeline_bedarf.py -k zahl -x` | ⚠️ extend existing |
| (AC2) | zahl always int∈[1,5], never empty | unit | `pytest tests/test_payment.py::test_zahl_range -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_payment.py -x -q`
- **Per wave merge:** `python3 -m pytest -q` (full suite — bedarf must stay green/untouched)
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_payment.py` — covers ZK-01/02/03 + Pitfall-16 misfire + conservative default + range/direction (new file)
- [ ] Extend `tests/test_reasons.py` — `reasons.build(verdicts, payment=...)` carries both rationales
- [ ] Extend `tests/test_pipeline_bedarf.py` — assert `analyze_row` emits real `zahl` (incl. empty-URL and exception-boundary rows)
- [ ] No framework install needed — pytest + `conftest.make_fetch_result` already present

## Security Domain

`security_enforcement` not set in config (no security gate configured). This phase processes no untrusted input beyond already-fetched HTML (parsed by bs4, already in use), adds no network/secrets, and writes no new external output. Relevant controls already satisfied by Phase 1–3:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | bs4 parses HTML safely; `re` patterns are ReDoS-free (`\b`-anchored, bounded — same discipline as `content.py` `{0,12}` cap) |
| V6 Cryptography | no | none added |

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ReDoS via crafted name/HTML | DoS | Use simple `\b`-anchored alternations, no nested quantifiers (matches existing `content.py` ReDoS note) |
| PII in logs/output | Info Disclosure | reason lists signals/assumptions, never raw scraped personal data (CLAUDE.md §6 / PITFALLS Pitfall 18) |

## Sources

### Primary (HIGH confidence)
- `lead_analyzer/pipeline.py`, `models.py`, `reasons.py`, `scoring.py`, `table_io.py`, `analyzers/content.py`, `analyzers/existence.py`, `config.py`, `tests/conftest.py`, `tests/test_content.py` — `[VERIFIED: read in this session]` integration points, conventions, offline test infra
- `.planning/REQUIREMENTS.md` — ZK-01/02/03, DIFF-01 deferred, Out of Scope `[VERIFIED]`
- `CLAUDE.md` — AC2/AC3/AC5/AC6, score definitions, §6 `[VERIFIED]`

### Secondary (MEDIUM confidence — project research docs)
- `.planning/research/FEATURES.md` — Zahlungskräftigkeit signal groups A/B/C, point ranges, combine map, conservative default `[CITED]`
- `.planning/research/ARCHITECTURE.md` — `analyzers/payment.py` placement, pure-analyzer + fetch-once patterns `[CITED]`
- `.planning/research/PITFALLS.md` — Pitfall 15 (hallucination), Pitfall 16 (legal-form misfire) `[CITED]`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; stdlib `re` + existing bs4
- Architecture/integration: HIGH — exact files/functions to edit are read and known
- Point values/tiers: MEDIUM — estimates by design (AC5); direction & traceability are firm, magnitudes tunable
- Pitfalls: HIGH — drawn from project's own verified pitfall research

**Research date:** 2026-06-14
**Valid until:** stable (offline, no external versions) — 30 days
