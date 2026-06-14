# Phase 3: Real Website-Bedarf Score (6 Dimensions) - Research

**Researched:** 2026-06-14
**Domain:** Deterministic HTML/header signal extraction + 1–5 aggregation (offline, no LLM, no new HTTP)
**Confidence:** HIGH (all signals are deterministic facts already present in the existing `FetchResult`; bs4 4.15.0 verified installed; aggregation formula traced against `docs/scoring_website_bedarf.md`)

## Summary

Phase 3 turns the provisional `bedarf_from_dim1` into the real six-dimension Website-Bedarf score. Everything needed already exists in one `FetchResult` per row (`fetch.py` captures `final_url`, `ssl_ok`, `headers`, `html`, `status`, `error`). The job is **fetch-once-parse-many**: add four pure analyzers (`technical.py` = Dim 2, `seo.py` = Dim 4, `ai_readiness.py` = Dim 5, `content.py` = Dim 6), a real `scoring.bedarf()` that aggregates six `DimensionVerdict`s, and a `reasons.py` that threads each verdict's reason into `RowResult.reason` and the output `Begründung` column. No new HTTP, no LLM, no new third-party dependency.

Two scope decisions are resolved below (also in the RESEARCH COMPLETE return): (1) **tldextract is rejected** — it requires a Public-Suffix-List download that breaks the offline guarantee and the test network-block; use a curated `FREE_SUBDOMAIN` set matched via `host.endswith(...)`, zero dependencies, fully offline-testable. (2) **Dim 3 stays out of aggregation as a fixed-`ok` placeholder in Phase 3** — Phase 6 owns PageSpeed; contributing a viewport heuristic now would either dilute monotonicity or force rework when real Dim 3 lands. A fixed `ok` (0 gap-points) keeps `G`/`S` bands stable and means Phase 6 can drop in real Dim-3 verdicts without re-tuning the band table.

**Primary recommendation:** Build 4 pure analyzers reading the existing `FetchResult`, a deterministic `scoring.bedarf(verdicts)` keyed on gap-points `G` + severe-count `S` with the FEATURES.md band table, and a `reasons.build()` joining all six verdict reasons. Parse the HTML **once** in `pipeline.analyze_row` (a single `BeautifulSoup`) and pass the parsed tree to all analyzers. Mirror the existing `existence.py` style: pure functions, German reason strings, `[CITED: ...]` provenance, offline fixtures via `make_fetch_result`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP fetch (Dim source) | fetch.py (already built) | — | One `FetchResult` per row; analyzers do zero I/O |
| Dim 2 Technische Basis | `analyzers/technical.py` | — | Pure: reads `final_url` scheme, `ssl_ok`, host |
| Dim 4 SEO | `analyzers/seo.py` | — | Pure: reads parsed HTML + `headers` (X-Robots-Tag) |
| Dim 5 KI-Readiness | `analyzers/ai_readiness.py` | — | Pure: reads parsed HTML (JSON-LD/OG/microdata) |
| Dim 6 Inhalt/Aktualität | `analyzers/content.py` | — | Pure: reads parsed HTML + `Last-Modified` header |
| HTML parse | `pipeline.analyze_row` | — | Parse once, pass tree to all analyzers (fetch-once-parse-many) |
| 1–5 aggregation | `scoring.bedarf()` | — | Pure deterministic G/S → band; dead-override |
| Traceability string | `reasons.py` | run-log (optional) | Single source of truth = the 6 verdicts |

## User Constraints (from objective + CLAUDE.md)

There is **no CONTEXT.md** for this phase (no `/gsd-discuss-phase` run). Constraints come from the objective brief and CLAUDE.md AC3/AC6/AC11:

### Locked Decisions
- Tool **and** tests fully offline. Tests mock `requests`; no network. **No PSL download → tldextract forbidden.**
- Deterministic, transparent scoring. **No LLM in this phase** (CLAUDE.md: transparency over elegance; LLM is v2 DIFF-02).
- Reuse the single `FetchResult` (fetch-once-parse-many). **No new HTTP** except possibly robots.txt/sitemap.xml — and those are **deferred** (recommendation below).
- Zahlungskräftigkeit stays on its Phase-1 placeholder (Phase 4 owns it).
- Dims 2 & 4 must be **really measured**; dims 5 & 6 at least heuristic (AC11).
- "No reachable website → 5" always overrides (already wired via `DimensionVerdict.dead`).
- Monotonic direction: more/bigger gaps ⇒ higher score; modern site → 1 (AC3, BED-08).

### Claude's Discretion
- Exact sub-signal → verdict combination rule per dimension (recommended below).
- Whether to add a run-log file now (recommended: **defer to Phase 5/7**; reason column suffices for NACH-01 in Phase 3).
- Reason-string format (compact for column, full for log).

### Deferred Ideas (OUT OF SCOPE for Phase 3)
- Dim 3 real PageSpeed/Lighthouse (Phase 6, BED-03).
- robots.txt / sitemap.xml fetches (extra HTTP — defer; single-page noindex still measured).
- LLM qualitative dim-6 layer (v2 DIFF-02).
- Zahlungskräftigkeit (Phase 4), cache/concurrency (Phase 5).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BED-02 | Dim 2 Technische Basis really measured: HTTPS + SSL + own vs free subdomain | §Dim 2 recipe; `final_url` scheme + `fr.ssl_ok` + `FREE_SUBDOMAIN` endswith set |
| BED-04 | Dim 4 SEO really measured: title/meta-desc, canonical, H1, noindex | §Dim 4 recipe; bs4 on parsed tree + `X-Robots-Tag` header. robots.txt/sitemap deferred |
| BED-05 | Dim 5 KI-readiness ≥ heuristic: JSON-LD, OG, microdata | §Dim 5 recipe; `script[type=application/ld+json]`, `og:*`, `itemscope` |
| BED-06 | Dim 6 Inhalt/Aktualität/Conversion ≥ heuristic: form, tel/mailto, Impressum, copyright/generator | §Dim 6 recipe; bs4 + copyright-year regex vs 2026 |
| BED-07 | Deterministic 6-dim aggregation per `docs/scoring_website_bedarf.md` bands; dead → 5 override | §Aggregation; G/S band table confirmed vs scoring doc |
| BED-08 | Monotonic direction (more gaps → higher); modern → 1, broken → 5 | §Direction tests; gradient fixtures |
| NACH-01 | Per-customer traceable reason (which dims drove the score) | §Traceability; `reasons.build()` → `RowResult.reason` → `Begründung` column |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| beautifulsoup4 | 4.15.0 (installed) | HTML parse for dims 2/4/5/6 | Already a project dep; already used in `existence.py` `[VERIFIED: .venv import]` |
| Python stdlib `json` | — | Parse JSON-LD `<script>` blocks | No dep; `@type` extraction |
| Python stdlib `re` | — | Copyright-year, generator detection | No dep |
| Python stdlib `urllib.parse.urlsplit` | — | Host extraction from `final_url` (free-subdomain check) | Already used in `existence.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 (installed) | Offline direction/unit tests | Existing suite (64 tests green) `[VERIFIED: pytest -q]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Curated `FREE_SUBDOMAIN` endswith set | `tldextract` (registrable domain) | **REJECTED** — downloads/refreshes Public-Suffix-List on first use → real network at import/runtime → breaks offline guarantee + `conftest` network block; adds a dependency. Curated endswith set is dependency-free, deterministic, offline-testable, and sufficient for the ~15 known builder hosts. `[VERIFIED: tldextract not installed in .venv]` |
| Single-page noindex (meta + `X-Robots-Tag`) | also fetch robots.txt + sitemap.xml | **DEFER** — extra HTTP per row breaks fetch-once and needs cache (Phase 5) for politeness/rate-limits. Single-page signals already satisfy BED-04 "really measured". Note robots/sitemap as Phase 5/6 optional. |
| Fixed-`ok` Dim 3 placeholder | viewport-meta heuristic now | **DEFER heuristic to Phase 6** — see Dim 3 decision below. Fixed `ok` keeps band table stable for Phase 6 drop-in. |

**Installation:** No new packages. (`bs4`, `requests`, `openpyxl` already in `requirements.txt`.)

**Version verification:** `beautifulsoup4` 4.15.0 confirmed importable in `.venv`; `tldextract` confirmed absent; `pytest` 9.0.3. `[VERIFIED: .venv/bin/python imports]`

## Architecture Patterns

### System Architecture Diagram

```
analyze_row(record, url_col, config)
   │  normalize URL  (empty → bedarf 5 "keine Website", no net)
   ▼
fetch.fetch(candidates) ──► FetchResult{final_url, ssl_ok, headers, html, status, error}
   │  (one fetch; never raises)
   │  PARSE ONCE:  soup = BeautifulSoup(fr.html, "html.parser")   [in pipeline]
   ▼
   ├─ existence.analyze(fr)            → Verdict dim1 (may set dead=True)
   │      └─ if dead → scoring.bedarf short-circuits to 5
   ├─ technical.analyze(fr)            → Verdict dim2   (final_url scheme, ssl_ok, host)
   ├─ (dim3 placeholder: Verdict(3,"ok","Performance: Phase 6"))
   ├─ seo.analyze(fr, soup)           → Verdict dim4   (title/meta/h1/canonical/lang/noindex)
   ├─ ai_readiness.analyze(soup)      → Verdict dim5   (json-ld/og/microdata)
   └─ content.analyze(fr, soup)       → Verdict dim6   (form/tel/mailto/impressum/copyright/generator)
        │
        ▼  verdicts = [v1..v6]
   scoring.bedarf(verdicts)  ──►  dead? 5 : band(G, S)   (1..5, monotonic)
   reasons.build(verdicts)   ──►  compact German string → RowResult.reason → Begründung column
```

File-to-responsibility mapping is in the Architectural Responsibility Map above.

### Recommended Project Structure (additions only)
```
lead_analyzer/
├── scoring.py            # ADD bedarf(verdicts) ; KEEP bedarf_from_dim1 until pipeline switches, then remove
├── reasons.py            # NEW: build(verdicts) → compact + full strings
└── analyzers/
    ├── technical.py      # NEW Dim 2
    ├── seo.py            # NEW Dim 4
    ├── ai_readiness.py   # NEW Dim 5
    └── content.py        # NEW Dim 6
tests/
├── test_technical.py     # NEW
├── test_seo.py           # NEW
├── test_ai_readiness.py  # NEW
├── test_content.py       # NEW
├── test_scoring_bedarf.py# NEW: G/S bands + dead override + direction/monotonic (BED-08)
└── test_reasons.py       # NEW
```

### Pattern 1: Pure analyzer over FetchResult (+ shared parsed soup)
**What:** Each analyzer is a pure function returning one `DimensionVerdict`. Dims that read HTML take the **already-parsed `soup`** so the tree is built once (fetch-once-**parse**-many).
**When to use:** All four new analyzers.
**Example:**
```python
# Source: pattern from existing lead_analyzer/analyzers/existence.py
from ..models import DimensionVerdict

def analyze(fr, soup) -> DimensionVerdict:   # seo.py (Dim 4)
    sub = []  # collect ("severe"|"gap"|"ok", note) sub-signals
    title = soup.title.get_text(strip=True) if soup.title else ""
    if not title:
        sub.append(("gap", "kein <title>"))
    # ... more sub-signals ...
    level, reason = _combine(sub, dim=4)
    return DimensionVerdict(4, level, reason, "html")
```

> **Parse-once note:** `existence.py` currently builds its own `BeautifulSoup` internally. For Phase 3, either (a) have `pipeline.analyze_row` build one `soup` and pass it to dims 4/5/6 (and optionally refactor existence to accept it), or (b) accept that existence parses once and the new analyzers share a second parse. Recommended: build `soup` once in the pipeline and pass it; refactor `existence.analyze` to accept an optional pre-parsed `soup` to fully honor fetch-once-parse-many. Guard for `fr.html is None` before parsing.

### Pattern 2: Sub-signal → dimension verdict combination rule
**What:** Within a dimension, fold N sub-signals into one of `ok|gap|severe`.
**Rule (deterministic, applies to dims 2/4/5/6):**
- **any** sub-signal is `severe` → dimension = `severe`
- else **≥2** sub-signals are `gap` → dimension = `gap`
- else **exactly 1** `gap` → dimension = `gap` (a single real gap still counts; matches FEATURES.md "≥1 Lücke → Lücke" for the simple dims)
- else → `ok`

> FEATURES.md line 113 says "any 2+ Lücke → Lücke; one minor flag → ok-with-note." Distinguish **real gaps** (missing title, no meta-desc, no structured data) from **minor flags** (missing canonical, missing `lang`, missing `tel:`). Recommendation: classify each sub-signal as `severe` / `gap` / `minor`. Combination: any `severe`→severe; else (≥1 `gap`)→gap; else (≥2 `minor`)→gap; else→ok. This keeps single cosmetic flags from inflating the score (monotonic, AC3) while a genuine missing-title is a gap on its own. **The planner must pin this rule explicitly per dimension** (sub-signal severity table below).

### Anti-Patterns to Avoid
- **Re-fetching or re-parsing per analyzer:** breaks fetch-once-parse-many (ARCHITECTURE.md Anti-Pattern 2). Parse once, pass `soup`.
- **Letting an analyzer raise:** `analyze_row` has the AC4 boundary, but analyzers should still be defensive (guard `None` html, malformed JSON-LD via `try/except json.JSONDecodeError`).
- **Coupling score direction to reason text:** keep the `dead` flag and `level` as the machine signal; reason is display only (existing models.py design; AC3).
- **Adding robots.txt/sitemap HTTP now:** extra network per row; defer.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Registrable-domain extraction | Custom PSL parser | Curated `FREE_SUBDOMAIN` endswith set | Full PSL needs a download (offline-breaking); only ~15 builder hosts matter here |
| HTML parsing / tag finding | Regex over HTML | bs4 `find`/`find_all`/`select` | Robust to malformed markup; already the project's tool |
| JSON-LD parsing | Regex for `@type` | `json.loads` on script contents (in `try/except`) | JSON-LD can be arrays/nested; regex is fragile |
| Date/freshness | Full date parser for `Last-Modified` | copyright-year regex `(20\d{2})` vs `2026` (primary); `Last-Modified` only corroborates | Copyright in footer is the reliable, offline freshness proxy |

**Key insight:** Every Phase-3 signal is a deterministic fact already inside `FetchResult`. The only "library temptation" (tldextract) is the one that breaks the offline contract — avoid it.

## Per-Dimension Extraction Recipes (plan-ready)

All recipes read from `fr` (`FetchResult`) and `soup` (parsed once). Sub-signal severity in **(severe / gap / minor)** classes per Pattern 2.

### Dim 2 — Technische Basis (`technical.py`) — BED-02
Inputs: `fr.final_url` (or `fr.url`), `fr.ssl_ok`, host.
```python
host = urlsplit(fr.final_url or fr.url or "").netloc.lower().removeprefix("www.")
scheme = urlsplit(fr.final_url or fr.url or "").scheme
```
| Sub-signal | Detect | Class |
|---|---|---|
| No HTTPS at all | final scheme == "http" | **severe** ("kein HTTPS") |
| Invalid/again-fallback SSL | `fr.ssl_ok is False` (fetch fell back to verify=False) | **severe** ("ungültiges SSL-Zertifikat") |
| Free/builder subdomain | `any(host == d or host.endswith("." + d) for d in FREE_SUBDOMAIN)` | **severe** ("Gratis-Subdomain {d}, keine eigene Domain") |
| Own domain + https + ssl_ok | none of the above | → `ok` ("eigene Domain, HTTPS, gültiges SSL") |

`FREE_SUBDOMAIN` (curated, dependency-free; `[CITED: FEATURES.md Dim-2]`):
```python
FREE_SUBDOMAIN = {
    "wixsite.com", "wix.com", "editorx.io", "jimdosite.com", "jimdofree.com",
    "business.site", "wordpress.com", "weebly.com", "webnode.page", "webnode.com",
    "squarespace.com", "square.site", "webflow.io", "github.io", "myshopify.com",
    "strikingly.com", "sitew.com", "webador.ch", "webador.com", "page.link",
    "blogspot.com", "yolasite.com", "ucraft.site", "mystrikingly.com",
}
```
Match rule: `host == d or host.endswith("." + d)` (the `.`-prefix prevents `evilwix.com` matching `wix.com`). Verdict: any severe → `severe`; else `ok`. (Dim 2 has no "minor" tier — HTTPS/SSL/own-domain are all hard.)

### Dim 4 — Auffindbarkeit SEO (`seo.py`) — BED-04
Inputs: `soup`, `fr.headers`.
| Sub-signal | Detect | Class |
|---|---|---|
| noindex (meta) | `soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})` content contains `noindex` | **severe** ("noindex – unsichtbar für Google") |
| noindex (header) | `fr.headers` key `X-Robots-Tag` (case-insensitive) contains `noindex` | **severe** |
| No `<title>` / empty | `soup.title` missing or empty text | **gap** ("kein/leerer Title") |
| Title length off | len ∉ ~[10,70] | **minor** ("Title-Länge {n}") |
| No meta description | no `<meta name="description">` with content | **gap** ("keine Meta-Description") |
| Meta-desc length off | len ∉ ~[50,160] | **minor** |
| H1 count ≠ 1 | `len(soup.find_all("h1")) != 1` (0 → gap, >1 → minor) | 0 → **gap**, >1 → **minor** |
| No canonical | no `<link rel="canonical">` | **minor** |
| No `<html lang>` | `soup.html` lacks `lang` attr | **minor** |

Header lookup must be case-insensitive: `next((v for k, v in fr.headers.items() if k.lower() == "x-robots-tag"), "")`. Verdict via Pattern 2.
**robots.txt / sitemap.xml:** DEFERRED (extra HTTP). Document as "Phase 5/6 optional".

### Dim 5 — KI-/Answer-Engine-Bereitschaft (`ai_readiness.py`) — BED-05
Inputs: `soup`.
```python
ld = soup.find_all("script", attrs={"type": "application/ld+json"})
types = set()
for s in ld:
    try:
        data = json.loads(s.string or s.get_text() or "")
    except (ValueError, TypeError):
        continue
    for obj in (data if isinstance(data, list) else [data]):
        if isinstance(obj, dict) and obj.get("@type"):
            t = obj["@type"]; types.update(t if isinstance(t, list) else [t])
og = soup.find_all("meta", property=re.compile(r"^og:", re.I))
microdata = bool(soup.find(attrs={"itemscope": True}) or soup.find(attrs={"itemtype": True}))
```
| Condition | Verdict |
|---|---|
| JSON-LD with a business `@type` (LocalBusiness/Organization/…) AND ≥3 OG tags | `ok` ("JSON-LD {types} + Open Graph vorhanden") |
| some OG tags OR microdata but no JSON-LD | `gap` ("nur Open Graph, kein JSON-LD") |
| nothing structured (no JSON-LD, no OG, no microdata) | `severe` ("kein strukturiertes Markup") |

### Dim 6 — Inhalt, Aktualität & Conversion (`content.py`) — BED-06
Inputs: `soup`, `fr.headers` (`Last-Modified` corroboration only). Current year = **2026** (use `datetime.now().year`, not a hardcoded literal, for forward-safety).
| Sub-signal | Detect | Class |
|---|---|---|
| No contact path | no `<form>` containing `input[type=email]`/`<textarea>` AND no link href/text matching `kontakt` | **gap** ("kein Kontaktformular/-pfad") |
| No `tel:` | no `a[href^=tel:]` | **minor** |
| No `mailto:` | no `a[href^=mailto:]` | **minor** |
| No Impressum/Datenschutz | no link text/href matching `impressum|rechtliches|datenschutz` | **gap** ("kein Impressum/Datenschutz") |
| Stale copyright | `re.search(r"(?:©|&copy;|copyright)[^\d]{0,12}(20\d{2})", html, re.I)` → newest year; `now-2..3` → gap, `≥4` → severe | **gap**/**severe** ("Copyright {year}, veraltet") |
| Legacy generator | `<meta name="generator">` matches legacy (`WordPress [1-5]\.`, `Joomla! [123]\.`, `Drupal 7`, `FrontPage`, `Dreamweaver`, `Mobirise`, free `Jimdo`) | **gap** ("veralteter Generator {g}") |
| Layout relic | `<frameset>`, `.swf` ref, or table-based layout heuristic | **minor** ("Layout-Relikt") |

Freshness staleness bands (relative to current year, AC-monotonic): `year >= now-1` → ok · `now-3 <= year <= now-2` → gap · `year <= now-4` → severe · no copyright found → minor (don't punish hard; many fine sites omit it). Verdict via Pattern 2.

## Aggregation (deterministic) — BED-07, BED-08

**Step 0 — dead override (highest priority):** if **any** verdict has `dead is True` (today only Dim 1 sets it) → return **5**. Stop. `[CITED: scoring doc "keine erreichbare Website überschreibt immer auf 5"; models.py dead flag]`

**Step 1 — gap-points per dimension:** `ok=0`, `gap=1`, `severe=2`.

**Step 2 — aggregate** total `G = sum(points)` and `S = count(level=="severe")` over the **scored** dimensions. With Dim 3 fixed at `ok` (0 points, see decision), the active dims are {1,2,4,5,6} plus Dim 3-as-ok. Max `G` for the 5 active dims = 10 (or 12 if Dim 3 ever contributes 2). Bands use the FEATURES.md table, which is calibrated for 6 dims (G 0–12):

| Condition | Score | Band (matches scoring doc lines 22–26) |
|---|---|---|
| any verdict `dead` | **5** | keine/defekte Website (override) |
| `G >= 7` OR `S >= 3` | **5** | schwere Mängel über mehrere Dimensionen |
| `4 <= G <= 6` OR `S == 2` | **4** | mehrere klare Lücken |
| `2 <= G <= 3` OR `S == 1` | **3** | spürbare Lücken in 1–2 Dimensionen |
| `G == 1` | **2** | weitgehend solide, kleine Schwäche |
| `G == 0` | **1** | modern über alle Dimensionen |

**Tie-break:** when the `G`-band and `S`-band disagree, take the **higher (more-bedarf)** score. A single site-wide noindex (`S==1` but maybe `G==2`) should not be diluted. Implement by computing both candidate scores and `return max(...)`. This guarantees monotonicity (AC3/BED-08): adding any gap can only raise or hold the score, never lower it.

**Verified monotonic against scoring doc:** band meanings line up 1:1 with `docs/scoring_website_bedarf.md` lines 20–28 (5=severe-multi, 4=multi-gap, 3=1–2 dims, 2=small, 1=modern). `[VERIFIED: cross-read scoring_website_bedarf.md ↔ FEATURES.md band table]`

### Dim 3 placeholder — RESOLVED DECISION
**Decision: Dim 3 contributes a fixed `DimensionVerdict(3, "ok", "Performance: erst Phase 6 (PageSpeed)", "heuristic-fallback")` = 0 gap-points, NOT counted as a gap.**

Rationale:
- **Monotonicity preserved (AC3):** a constant 0 never perturbs ordering between rows.
- **No rework in Phase 6:** the band table is already sized for 6 dims (G 0–12). When Phase 6 replaces the placeholder with real `ok/gap/severe` from PageSpeed (+viewport fallback), `G`/`S` simply gain a real contributor — no band re-tuning.
- **Alternative rejected:** contributing the viewport-meta heuristic now (absent→gap) would (a) penalize sites Phase 6 might rate fast, and (b) get overwritten anyway. Defer the heuristic to Phase 6 where it's the documented fallback for "no PSI key/network."
- AC11 is still satisfied: it requires dims **1–4** really measured (1,2,4 are; 4 single-page-measured) and 5/6 ≥ heuristic. Dim 3 real measurement is explicitly Phase 6 (BED-03) per the roadmap and REQUIREMENTS traceability.

Make the placeholder a named constant so Phase 6 swaps one line:
```python
DIM3_PLACEHOLDER = DimensionVerdict(3, "ok", "Performance: erst Phase 6 (PageSpeed)", "heuristic-fallback")
```

## Traceability — NACH-01 / AC6 (`reasons.py`)

Single source of truth: the six `DimensionVerdict`s already on `RowResult.verdicts`. `reasons.build` derives both forms so score and explanation can never diverge.

**Compact (Begründung column):** join non-`ok` dims, e.g.
`Dim2 schwere Lücke (Gratis-Subdomain wixsite.com); Dim4 Lücke (keine Meta-Description, 0×H1); Dim6 Lücke (Copyright 2021, veraltet) → G=4, Bedarf 4`
If all `ok`: `alle Dimensionen ok → Bedarf 1`. Keep ≤ ~200 chars (truncate gracefully).

**Full (run-log line, if/when a log exists):** one line per dim: `dim, level, source, reason` + `G`, `S`, final score.

**Threading into output:** `pipeline.analyze_row` already builds `RowResult(reason=..., verdicts=[...])`; `table_io.write_output` already emits a `Begründung` column from `result.reason` (`reason_column=config.reason_column`, verified in table_io lines 133–171). So Phase 3 only needs to set `reason = reasons.build(verdicts)` instead of the current single `verdict.reason`.

**Run-log file — recommendation: DEFER.** A dedicated run-log (`output/run-<ts>.log`) is nice-to-have but ARCHITECTURE.md schedules logging with hardening; the **Begründung column alone satisfies NACH-01/AC6** ("Begründungsspalte **und/oder** Lauf-Log"). Keep `RowResult.verdicts` populated now so a Phase-5/7 log can be added without re-plumbing. If the planner wants belt-and-braces, a `logging.getLogger(__name__).info(...)` per row is a small, optional add — not required for the AC.

## Common Pitfalls

### Pitfall 1: tldextract sneaks the network back in
**What goes wrong:** `tldextract` lazily downloads the Public Suffix List on first call → a real HTTP request → fails the `conftest` network block and breaks offline runs.
**How to avoid:** Use the curated `FREE_SUBDOMAIN` endswith set. No PSL, no dependency. `[VERIFIED: tldextract absent from .venv]`

### Pitfall 2: Parsing HTML per analyzer
**What goes wrong:** each dim builds its own `BeautifulSoup` → wasted CPU, and conceptually violates fetch-once-parse-many.
**How to avoid:** Parse once in `analyze_row`, pass `soup` to dims 4/5/6 (and ideally refactor existence to accept it). Guard `fr.html is None`.

### Pitfall 3: `noindex` only checked in HTML, not headers
**What goes wrong:** `X-Robots-Tag: noindex` (header-level) hides a site from Google but isn't in the HTML — missing it under-scores a real severe gap.
**How to avoid:** Check both the `<meta name=robots>` tag AND `fr.headers` (case-insensitive key lookup).

### Pitfall 4: Non-monotonic aggregation from competing G/S bands
**What goes wrong:** computing only the G-band lets a single severe gap (S=1, low G) under-score.
**How to avoid:** Compute both G-band and S-band candidate scores, `return max(...)`. Unit-test the gradient (BED-08).

### Pitfall 5: Malformed JSON-LD crashes Dim 5
**What goes wrong:** `json.loads` on a broken `<script type=ld+json>` raises.
**How to avoid:** wrap in `try/except (ValueError, TypeError)`, skip the block; absence of valid JSON-LD is itself a signal.

### Pitfall 6: Hardcoding year 2026
**What goes wrong:** copyright freshness silently wrong next year.
**How to avoid:** `datetime.now().year`. (Brief says "current year 2026" — that's today's value, not a literal.)

## Code Examples

### Aggregation core (scoring.py)
```python
# Source: derived from FEATURES.md band table + scoring_website_bedarf.md
_POINTS = {"ok": 0, "gap": 1, "severe": 2}

def bedarf(verdicts: list[DimensionVerdict]) -> int:
    if any(v.dead for v in verdicts):
        return 5
    G = sum(_POINTS[v.level] for v in verdicts)
    S = sum(1 for v in verdicts if v.level == "severe")
    g_score = (5 if G >= 7 else 4 if G >= 4 else 3 if G >= 2 else 2 if G == 1 else 1)
    s_score = (5 if S >= 3 else 4 if S == 2 else 3 if S == 1 else 1)
    return max(g_score, s_score)   # tie-break toward more Bedarf (monotonic, AC3)
```

### Free-subdomain check (technical.py)
```python
def _is_free_subdomain(host: str) -> str | None:
    host = host.lower().removeprefix("www.")
    for d in FREE_SUBDOMAIN:
        if host == d or host.endswith("." + d):
            return d
    return None
```

## State of the Art

| Old Approach | Current Approach | When | Impact |
|---|---|---|---|
| tldextract for registrable domain | curated endswith set | this phase | keeps offline guarantee |
| provisional `bedarf_from_dim1` | full `bedarf(verdicts)` over 6 dims | this phase | satisfies BED-07; remove old fn after pipeline switch |
| CrUX field data in PSI | Lighthouse lab scores (Phase 6) | — | not in Phase 3; noted for Phase 6 |

**Deprecated/outdated:**
- `scoring.bedarf_from_dim1` and `placeholder_result` bedarf path: superseded by `bedarf()`; keep `placeholder_result` only for the `zahl` placeholder until Phase 4, or extract a `zahl_placeholder()` helper.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Title good-length ~10–70, meta-desc ~50–160 are "minor" not "gap" thresholds | Dim 4 | Low — only nudges minor flags; planner can tune; monotonicity unaffected |
| A2 | Copyright staleness bands (now-1 ok / now-2..3 gap / ≤now-4 severe) | Dim 6 | Low — heuristic by AC11; tune against sample |
| A3 | FREE_SUBDOMAIN list is "complete enough" for Swiss SME builders | Dim 2 | Medium — a missed builder host under-scores; mitigate by easy extensibility + sample check |
| A4 | Begründung column alone satisfies NACH-01 (no log file needed in Phase 3) | Traceability | Low — REQUIREMENTS says "Spalte und/oder Log"; column qualifies |
| A5 | Dim 3 fixed-`ok` placeholder is acceptable for AC11 (1–4 measured: 1,2,4 yes; 3 = Phase 6) | Dim 3 decision | Low — REQUIREMENTS traceability puts BED-03 in Phase 6 explicitly |
| A6 | Sub-signal 3-tier (severe/gap/minor) combination is the intended "1–2 dimension" calibration | Pattern 2 | Medium — affects exact scores; planner must pin the per-dim severity table and verify against sample (SETUP-02, Phase 7) |

## Open Questions

1. **Exact per-dimension sub-signal severity table.**
   - What we know: the signals and the 3-tier combination rule.
   - What's unclear: minor-vs-gap classification of borderline signals (e.g. is missing canonical "minor" or "gap"?).
   - Recommendation: planner pins a per-dim severity table (this research proposes one); final calibration validated against `data/sample_input.xlsx` in Phase 7 (SETUP-02). Phase 3 only needs internal consistency + monotonic tests.

2. **Refactor existence to accept pre-parsed soup?**
   - What we know: existence currently parses internally.
   - Recommendation: yes, pass `soup` to fully honor parse-once; small change, keeps tests green (existence already takes `fr`; add optional `soup=None` param that parses if not given → backward compatible).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| beautifulsoup4 | dims 4/5/6 parse | ✓ | 4.15.0 | — |
| Python stdlib (json/re/urllib) | all dims | ✓ | 3.x | — |
| pytest | offline tests | ✓ | 9.0.3 | — |
| tldextract | (rejected) | ✗ | — | curated FREE_SUBDOMAIN set |
| network | — | n/a (forbidden in phase) | — | all signals from cached FetchResult |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** tldextract → curated set (by design).

## Validation Architecture

`workflow.nyquist_validation` is `true` → this section applies.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 `[VERIFIED]` |
| Config file | none detected (pytest default discovery; tests/ at repo root) |
| Quick run command | `.venv/bin/python -m pytest tests/test_scoring_bedarf.py -q` |
| Full suite command | `.venv/bin/python -m pytest -q` |

Network is blocked by `tests/conftest.py` autouse fixture → all Phase-3 tests are inherently offline; analyzers consume `make_fetch_result(html=..., headers=..., ssl_ok=..., final_url=...)`.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BED-02 | http→severe; ssl_ok False→severe; wixsite host→severe; clean→ok | unit | `pytest tests/test_technical.py -x` | ❌ Wave 0 |
| BED-04 | missing title/meta/H1→gap; meta+header noindex→severe; clean→ok | unit | `pytest tests/test_seo.py -x` | ❌ Wave 0 |
| BED-05 | JSON-LD+OG→ok; OG-only→gap; nothing→severe; malformed JSON-LD no crash | unit | `pytest tests/test_ai_readiness.py -x` | ❌ Wave 0 |
| BED-06 | no form/impressum→gap; stale copyright→gap/severe; legacy generator→gap; year via datetime | unit | `pytest tests/test_content.py -x` | ❌ Wave 0 |
| BED-07 | dead→5 override; G/S bands map to 1–5; matches scoring doc | unit | `pytest tests/test_scoring_bedarf.py -x` | ❌ Wave 0 |
| BED-08 | monotonic gradient: all-ok→1; worsening→non-decreasing; all-severe/dead→5 | unit | `pytest tests/test_scoring_bedarf.py::test_monotonic -x` | ❌ Wave 0 |
| NACH-01 | reasons.build lists driving non-ok dims; threads into RowResult.reason | unit | `pytest tests/test_reasons.py -x` | ❌ Wave 0 |
| (wiring) | analyze_row uses all 6 verdicts + new bedarf; offline integration | integration | `pytest tests/test_pipeline_dim1.py -q` (extend) | ⚠️ extend |

### Sampling Rate
- **Per task commit:** the matching new `tests/test_*.py` for the analyzer/scoring touched.
- **Per wave merge:** `.venv/bin/python -m pytest -q` (full suite; must stay green, currently 64).
- **Phase gate:** full suite green before `/gsd-verify-work`; plus a documented offline sample reasoning (sample run is SETUP-02/Phase 7, but Phase 3 should add a few crafted FetchResult fixtures proving modern→1 and broken→5).

### Wave 0 Gaps
- [ ] `tests/test_technical.py` — covers BED-02
- [ ] `tests/test_seo.py` — covers BED-04
- [ ] `tests/test_ai_readiness.py` — covers BED-05
- [ ] `tests/test_content.py` — covers BED-06
- [ ] `tests/test_scoring_bedarf.py` — covers BED-07, BED-08 (bands + dead + monotonic gradient)
- [ ] `tests/test_reasons.py` — covers NACH-01
- [ ] Extend `tests/test_pipeline_dim1.py` (or new `test_pipeline_bedarf.py`) for the 6-dim wiring
- No framework install needed (pytest present). No new fixtures beyond `make_fetch_result` (extend overrides for `headers`/`ssl_ok`/`final_url`, all already supported).

## Security Domain

`security_enforcement` not present in config → treat as enabled. This phase has a narrow surface: parsing untrusted third-party HTML offline (no execution, no storage of secrets, no auth).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Untrusted HTML/JSON-LD parsed defensively: bs4 (no eval), `json.loads` in try/except, body already byte-capped (2 MB in fetch.py), no `eval`/`exec` |
| V6 Cryptography | no (read-only) | TLS validity is a *signal* (`ssl_ok`), already handled in fetch.py; no crypto authored here |

### Known Threat Patterns for offline HTML parsing
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/huge HTML (DoS) | DoS | 2 MB body cap already in fetch.py; bs4 `html.parser` tolerant |
| Malformed JSON-LD | Tampering | `json.loads` wrapped in try/except; skip block |
| XXE / entity expansion | Tampering/DoS | Use `html.parser` (not lxml-xml); no external entity resolution |
| Regex catastrophic backtracking | DoS | Keep copyright/generator regexes linear/anchored, bounded `{0,12}` quantifiers |
| ReDoS via attacker HTML | DoS | Avoid nested unbounded quantifiers; test on adversarial fixture |

No secrets, no PII persistence in this phase (CLAUDE.md §6: local only; outputs gitignored — unchanged).

## Sources

### Primary (HIGH confidence)
- `docs/scoring_website_bedarf.md` — 6-dimension rubric + aggregation bands + edge-cases (authoritative)
- `CLAUDE.md` — AC3/AC6/AC11
- `.planning/research/FEATURES.md` — concrete per-dim signal tables + G/S band formula + reason format
- `.planning/research/ARCHITECTURE.md` — analyzers package, fetch-once-parse-many, models, anti-patterns
- Existing code: `lead_analyzer/{models,scoring,pipeline,fetch}.py`, `analyzers/existence.py`, `tests/conftest.py`, `table_io.py` (verdict/dead flag, reason column, network-block fixture) — read this session
- `.venv` import checks: `beautifulsoup4` 4.15.0 present, `tldextract` absent, `pytest` 9.0.3, 64 tests green `[VERIFIED]`

### Secondary (MEDIUM confidence)
- FEATURES.md cited free-builder host list (sitebuilderreport / WebBuildersGuide) — used for `FREE_SUBDOMAIN` seed

### Tertiary (LOW confidence)
- none

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; bs4 verified installed
- Architecture: HIGH — directly follows established `existence.py`/ARCHITECTURE.md patterns
- Aggregation: HIGH — band table cross-verified against scoring doc; monotonic by construction
- Pitfalls: HIGH — tldextract/offline and noindex-header risks verified against code + env
- Sub-signal calibration: MEDIUM — exact minor/gap thresholds are tunable (A1/A6), validated in Phase 7 sample run

**Research date:** 2026-06-14
**Valid until:** ~2026-07-14 (stable; internal-codebase-driven, no fast-moving external deps)
