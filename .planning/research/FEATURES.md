# Feature Research

**Domain:** Local CLI scoring engine for Swiss SME websites (lead qualification for "MyWEBSITE")
**Researched:** 2026-06-14
**Confidence:** HIGH (signals 1–4, 5, 6 are deterministic HTTP/HTML facts; MEDIUM on PageSpeed thresholds and Zahlungskräftigkeit tiers, which are estimates by design per AC5)

This file translates the six **Website-Bedarf** dimensions (`docs/scoring_website_bedarf.md`) and the **Zahlungskräftigkeit** score into concrete, implementable signals, plus a deterministic 1–5 aggregation formula. It maps directly to acceptance criteria **AC3** (score direction), **AC5** (purchasing power = documented public estimate), and **AC11** (Bedarf from six dimensions; dims 1–4 really measured).

---

## How to read the signal tables

Each dimension produces a **per-dimension verdict**: `ok` / `Lücke` / `schwere Lücke` (and for dim 1, `dead` which triggers the override). The signals below are the inputs to that verdict. Everything in "Table Stakes" must be implemented to satisfy AC11. Differentiators are optional enrichment. Anti-features are explicitly out.

**One fetch, reused everywhere:** a single `requests.get` (with redirects followed) per URL yields the final URL, status, headers, TLS info, and HTML. Parse the HTML once with BeautifulSoup; feed the parsed tree to dims 1, 2, 4, 5, 6. Dim 3 (and Lighthouse-SEO sub-signal of dim 4) come from one PageSpeed Insights call. So the whole engine is **2 network calls per customer max** (HTTP fetch + PSI), both cacheable (AC7).

---

## Feature Landscape

### Table Stakes (Required to satisfy AC11 — dims 1–4 must be REALLY measured)

#### Dimension 1 — Existenz & Substanz  (the override dimension)

| Signal | How to detect (concrete) | Verdict mapping | Complexity |
|---|---|---|---|
| Empty / missing URL | Cell blank, NaN, or not URL-shaped after trim | `dead` → score 5, note "keine Website" | LOW |
| URL normalization before judging | Try in order: `https://{host}`, `https://www.{host}`, `http://{host}`, `http://www.{host}`. Add scheme if missing. Strip stray chars. (Sample has `htp://naehatelier-sutter` → fix scheme typo `htp`→`http`, then DNS-resolve; if no resolution → dead) | If none reachable → `dead` | MEDIUM |
| Reachable | Final response `status_code == 200` (after redirects). 3xx that lands on 200 = reachable; 4xx/5xx/DNS-fail/ConnectionError/Timeout = not reachable | not reachable → `dead`, note "nicht erreichbar" | LOW |
| Parked / placeholder domain | Match markers in final URL host or HTML: registrar parking hosts (`sedoparking.com`, `parkingcrew`, `bodis`, `above.com`, `dan.com`, `afternic`), title/body phrases ("Diese Domain", "Domain parken", "is for sale", "buy this domain", "Website coming soon", "Under construction", "Standardseite"/default Apache/Nginx/IIS welcome pages), or HTML body < ~512 chars of visible text | parked → treat as `dead` (note "geparkt") | MEDIUM |
| Social-media-only | Final URL host in {`facebook.com`, `fb.com`, `instagram.com`, `linktr.ee`, `linkedin.com`, `tiktok.com`, `t.me`} OR input URL itself is such a host | `schwere Lücke` (NOT dead — there is *some* presence), note "Social-only", contributes strongly toward score 5 | LOW |
| Thin content | Visible text after stripping nav/script < ~300 words, or single-page with no internal links | `Lücke` | LOW |

**Override rule (AC11 + scoring doc):** verdict `dead` (no/parked/unreachable site) → **final score = 5**, skip all other dimensions, record the reason. This is the only hard override.

#### Dimension 2 — Technische Basis

| Signal | How to detect (concrete) | Verdict mapping | Complexity |
|---|---|---|---|
| HTTPS reachable | Did the working URL use `https`? | http-only or https failed → `Lücke` (or `schwere Lücke` if no https at all) | LOW |
| Valid TLS certificate | `requests.get(url)` succeeds without `SSLError`. For detail: `ssl.create_default_context().wrap_socket(...)` to host:443, read `getpeercert()` → check `notAfter` not expired and hostname matches. Expired/self-signed/mismatch raises → catch | invalid/expired cert → `schwere Lücke` | MEDIUM |
| Redirect http→https | Request `http://` and check final scheme is `https` | no auto-upgrade → minor flag (folds into the HTTPS verdict) | LOW |
| Free / builder subdomain (not own domain) | Final registrable domain ends in one of: `wixsite.com`, `wix.com` (editorx), `jimdosite.com`, `jimdo.com`, `business.site` (Google), `wordpress.com`, `weebly.com`, `webnode.page` / `webnode.com`, `squarespace.com`, `square.site`, `webflow.io`, `github.io`, `myshopify.com`, `wordpress.com`, `strikingly.com`, `sitew.com`, `webador.ch/.com`, `1g1.ms` / `ionos` builder, `companysites.ch`. Compare via `tldextract` registrable domain | on free subdomain → `schwere Lücke` (strong MyWEBSITE pitch: "eigene Domain") | LOW |
| Own domain confirmation | Registrable domain not in the free list AND not a social host | reinforces `ok` | LOW |

#### Dimension 3 — Mobile & Performance  (PageSpeed Insights API)

| Signal | How to detect (concrete) | Threshold → verdict | Complexity |
|---|---|---|---|
| Viewport meta (responsive) | Parse HTML for `<meta name="viewport" content="...width=device-width...">`. Absent → not mobile-ready (cheap, works without PSI) | missing → at least `Lücke` regardless of PSI | LOW |
| PSI call | `GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile&category=performance&category=seo&key={PAGESPEED_API_KEY}` (keyless works but ~ very low quota — batch + backoff per AC8) | — | MEDIUM |
| Lighthouse Performance score | `lighthouseResult.categories.performance.score` (0.0–1.0) | `>=0.90` ok · `0.50–0.89` Lücke · `<0.50` schwere Lücke | LOW |
| LCP (lab) | `lighthouseResult.audits["largest-contentful-paint"].numericValue` (ms) | `<=2500` ok · `2500–4000` Lücke · `>4000` schwere Lücke | LOW |
| CLS (lab) | `lighthouseResult.audits["cumulative-layout-shift"].numericValue` | `<=0.1` ok · `0.1–0.25` Lücke · `>0.25` schwere Lücke | LOW |
| TBT (lab, interactivity proxy) | `lighthouseResult.audits["total-blocking-time"].numericValue` (ms) | `<=200` ok · `200–600` Lücke · `>600` schwere Lücke | LOW |
| Field/CrUX data (BONUS) | `loadingExperience.metrics.{LARGEST_CONTENTFUL_PAINT_MS, CUMULATIVE_LAYOUT_SHIFT_SCORE, INTERACTION_TO_NEXT_PAINT}.category` = `FAST`/`AVERAGE`/`SLOW`. **Often empty for low-traffic SME sites** and Google is phasing CrUX out of PSI — use only as a bonus when present, never as the primary signal | present+SLOW → push toward schwere Lücke | LOW |

> **Verified:** category scores live at `lighthouseResult.categories.<id>.score`; metric values at `lighthouseResult.audits.<id>.numericValue`; CrUX at `loadingExperience.metrics.<METRIC>.category`. Source: Google PSI v5 docs. Use mobile strategy (SME customers' visitors are mostly mobile, and "Responsive" is a core MyWEBSITE promise).

**Dim 3 fallback without PSI key/network:** use viewport-meta only → present = `ok`-ish but tentative, absent = `Lücke`; mark note "Performance heuristisch (kein PSI)". This keeps AC4/AC11 satisfied (dim 3 still measured at the HTML level).

#### Dimension 4 — Auffindbarkeit (SEO)

| Signal | How to detect (concrete) | Verdict contribution | Complexity |
|---|---|---|---|
| `<title>` present + length | Parse `<title>`. Good: present, ~30–60 chars. Missing/empty → strong flag; too short (<10) or too long (>70) → minor flag | missing → Lücke | LOW |
| Meta description present + length | `<meta name="description">`. Good ~50–160 chars. Missing → flag | missing → Lücke | LOW |
| Exactly one H1 | Count `<h1>`. 0 or >1 → flag | 0 H1 → Lücke | LOW |
| Canonical | `<link rel="canonical">` present | absent → minor | LOW |
| robots.txt | `GET /robots.txt` → 200 and not blocking all (`Disallow: /` for `*`) | missing → minor; `Disallow: /` site-wide → schwere Lücke (invisible to Google) | LOW |
| sitemap.xml | `GET /sitemap.xml` → 200, or referenced in robots.txt | absent → minor | LOW |
| noindex (critical) | `<meta name="robots" content="...noindex...">` OR `X-Robots-Tag: noindex` header | present → `schwere Lücke` (site deliberately hidden) | LOW |
| `lang` attribute | `<html lang="...">` present | absent → minor | LOW |
| Lighthouse SEO score (BONUS) | `lighthouseResult.categories.seo.score` from the same PSI call | `>=0.9` ok · `0.7–0.9` Lücke · `<0.7` schwere Lücke. Use to corroborate the HTML-parse verdict | LOW |

#### (Dim 4 is the last of the "must be REALLY measured" set per AC11 — all of dims 1–4 above are deterministic HTTP/HTML/PSI facts, satisfying AC11's "Dim. 1–4 real gemessen".)

#### Dimension 5 — KI-/Answer-Engine-Bereitschaft  (heuristic OK per AC11)

| Signal | How to detect (concrete) | Verdict contribution | Complexity |
|---|---|---|---|
| JSON-LD structured data | `soup.find_all("script", type="application/ld+json")` → parse JSON, check for `@type` (LocalBusiness, Organization, etc.) | none → `Lücke` (key for AI/answer engines) | LOW |
| Microdata | Attributes `itemscope` / `itemtype` present in HTML | present reinforces ok | LOW |
| Open Graph tags | `<meta property="og:title">`, `og:description`, `og:image`, `og:type` | none → `Lücke` | LOW |
| Twitter cards (minor) | `<meta name="twitter:card">` | bonus only | LOW |

Verdict: rich (JSON-LD LocalBusiness + OG complete) → `ok`; some OG but no JSON-LD → `Lücke`; nothing structured → `schwere Lücke`.

#### Dimension 6 — Inhalt, Aktualität & Conversion  (heuristic OK per AC11)

| Signal | How to detect (concrete) | Verdict contribution | Complexity |
|---|---|---|---|
| Contact form | `<form>` containing an `<input type="email">`/`textarea`, OR a link to a `/kontakt` page | absent → Lücke (no conversion path) | LOW |
| `tel:` link | `a[href^="tel:"]` | absent → minor | LOW |
| `mailto:` link | `a[href^="mailto:"]` | absent → minor | LOW |
| Impressum (Swiss) | Link text/href matching `impressum`, `kontakt`, `rechtliches`, `datenschutz`. Swiss UWG requires identification; absence is a real gap | absent → Lücke | LOW |
| Freshness — copyright year | Regex `©\s*(20\d{2})` or `Copyright ... 20\d{2}` in footer. Compare to current year (2026). `>=2 years stale` → Lücke; `>=4 years` → schwere Lücke | older → Lücke/schwere Lücke | LOW |
| Freshness — Last-Modified header | `Last-Modified` response header date; if very old, freshness flag | corroborates copyright | LOW |
| Outdated builder / generator | `<meta name="generator">` content. Flag legacy: old WordPress (`WordPress 4.x`/`5.x`), `Joomla! 1.x/2.x/3.x`, `Drupal 7`, `FrontPage`, `Adobe GoLive`, `Dreamweaver`, `Mobirise`, `Jimdo` (free), table-based layout. Modern (current WP 6.x, Webflow, Next.js, Hugo) → ok | legacy generator → Lücke | LOW |
| Table-layout / Flash relic | Presence of `<table>` used for layout, `<frameset>`, or `.swf` references | strong staleness flag | LOW |

---

### Aggregation: per-dimension verdicts → 1–5 integer (deterministic, AC3 + AC11)

**Step 0 — Override (highest priority):** if dim 1 verdict is `dead` → **score = 5**, reason = the dead cause (keine Website / nicht erreichbar / geparkt). Stop.

**Step 1 — Score each of the 6 dimensions** to a numeric weight:
- `ok` = 0 gap points
- `Lücke` = 1 gap point
- `schwere Lücke` = 2 gap points

(Within a dimension, combine its sub-signals to one verdict: any `schwere Lücke` sub-signal → dimension = schwere Lücke; else any 2+ `Lücke` sub-signals → Lücke; one minor flag → ok-with-note.)

**Step 2 — Aggregate** total gap points `G` (range 0–12, since 6 dims × max 2) **and** count of dimensions with a `schwere Lücke` (`S`):

| Condition | Score | Band meaning (matches scoring doc) |
|---|---|---|
| dim1 = dead | **5** | keine/defekte Website (override) |
| `G >= 7` OR `S >= 3` | **5** | schwere Mängel über mehrere Dimensionen |
| `4 <= G <= 6` OR `S == 2` | **4** | mehrere klare Lücken |
| `2 <= G <= 3` OR `S == 1` | **3** | spürbare Lücken in 1–2 Dimensionen |
| `G == 1` | **2** | weitgehend solide, kleine Schwäche |
| `G == 0` | **1** | modern über alle Dimensionen |

Tie-break rule: when a row's `G` band and `S` band disagree, take the **higher** (more-bedarf) score — a single severe gap (e.g. site-wide noindex) should not be diluted by otherwise-fine dimensions. This keeps AC3 direction monotonic.

**Traceability output (AC6/AC11):** emit a per-customer reason string listing each dimension's verdict + the driving signal, e.g. `Dim2:schwere Lücke(free wixsite.com subdomain); Dim3:Lücke(perf 0.61, no LCP issue); Dim4:Lücke(no meta description, no H1); G=4 → 4`. Put a short version in an optional `Begründung` column and the full version in the run log.

---

### Zahlungskräftigkeit (Score 2) — public signals as a *documented estimate* (AC5)

AC5 forbids invented facts: every point must trace to a public, named signal or a labelled conservative assumption. Three signal groups, combined heuristically, each logged.

**A. Legal form from company-name suffix** (free, deterministic, parse `Kundenname`):

| Suffix in name | Implies | Base points |
|---|---|---|
| `AG` (Aktiengesellschaft) | min. CHF 100k capital, formal structure → higher capacity | +2 |
| `GmbH` | min. CHF 20k capital, established KMU | +1 |
| `Sàrl` / `SA` (Romandie equivalents of GmbH/AG) | same as GmbH/AG | +1 / +2 |
| `& Co` / `KlG` / `Kollektivges.` | partnership, mid | +0.5 |
| No suffix / personal name / `Einzelfirma` | sole proprietor, lower capacity | 0 |

> Document the rule, not a fact: "Name endet auf 'AG' → Rechtsform Aktiengesellschaft angenommen (Quelle: Firmenname)". This is an *assumption from the name*, clearly labelled — compliant with AC5.

**B. Industry purchasing-power tier** (branch from `Branche` column; tiers are documented estimates):

| Tier | Branches (from the sample) | Points |
|---|---|---|
| High | Zahnarzt, Treuhand, Immobilien, Garage (Auto) | +2 |
| Medium | Schreinerei, Sanitär, Gartenbau, Handwerk (allg.), Maler, Confiserie | +1 |
| Lower | Bäckerei, Coiffeur, Velo, Floristik, Detailhandel | 0 |

> Tiers reflect typical margins/ticket-size, not a specific firm's finances — label as "Branchen-Tier (Annahme)". Sales can override.

**C. Website-derived size signals** (from the same fetched HTML — free, factual):

| Signal | Detect | Points |
|---|---|---|
| Multiple locations | Several addresses / "Standorte" / city list on contact page | +1 |
| Team / staff page | `/team`, `/mitarbeiter`, `/ueber-uns` listing multiple people | +0.5 |
| Careers / hiring | `/jobs`, `/karriere`, "offene Stellen" | +0.5 |
| Fleet / equipment | Vehicle fleet, machinery gallery (Garage, Gartenbau, Sanitär) | +0.5 |
| Own domain + professional site | (already computed in dim 2) | +0.5 |

**Combine → 1–5:** sum A+B+C (cap), then map:
`total >= 4 → 5`, `3 → 4`, `2 → 3`, `1 → 2`, `<=0 → 1`.
Default when nothing resolvable: **conservative 2–3** with note "konservative Schätzung, dünne Datenlage" (AC5: fehlt Datenlage → konservativ + kennzeichnen).

**Differentiator (optional): Zefix live lookup** — query the public Zefix (Zentraler Firmenindex) search to confirm legal form, founding year, and status. Public, factual, citable. Use to *upgrade* a name-based assumption to a confirmed fact in the log. Rate-limit + cache (AC7/AC8). Keep optional so the tool runs with no network (graceful degradation per Constraints).

---

## Differentiators (Competitive Advantage — optional enrichment, never required for AC11)

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| LLM qualitative layer for dim 6 | Judge text quality / professionalism / outdatedness beyond regex; summarize the *why* for the Begründung column | MEDIUM | Only when `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` set; run AFTER deterministic checks, as add-on (scoring doc §16) |
| Zefix live company lookup | Turns name-based legal-form *assumption* into a *confirmed public fact* (AC5 upside) | MEDIUM | Public registry; cache + backoff |
| Screenshot capture (mobile) | Visual proof of outdated/broken layout for sales; can feed a vision LLM | HIGH | Needs headless browser (Playwright) — heavy dep; defer |
| PSI API key support | Lifts the keyless quota so AC1 (hundreds of rows) is reliable | LOW | `.env` `PAGESPEED_API_KEY`; batch + backoff (AC8) |
| Per-dimension column breakout | Six extra columns (one verdict per dim) for power-sorting | LOW | Optional; CLAUDE.md requires only the 2 score columns |

## Anti-Features (Deliberately NOT built)

| Feature | Why tempting | Why problematic | Instead |
|---|---|---|---|
| Headless-browser render for *every* row | "Real" rendering, JS sites | Slow, heavy dep, breaks AC1 at scale, fragile | Static HTML parse + PSI (PSI already renders); screenshots only as opt-in differentiator |
| Real credit/bonitäts data (CRIF/Bisnode/Moneyhouse paid) | "Accurate" purchasing power | Paid, licensing, AC5 says *estimate not audit*, scope §6 ("kein Bonitäts-Audit") | Documented heuristic A+B+C + optional free Zefix |
| Mandatory LLM scoring | "Smart" scores | Blackbox vs. transparency principle; cost; non-reproducible | Deterministic core, LLM only as labelled add-on |
| Web dashboard / live monitoring / Salesforce sync | Looks complete | Explicitly out of scope (CLAUDE.md §6) | CLI: Excel in → Excel out |
| Scraping deep multi-page crawls per site | "More signals" | Slow, rate-limit risk, AC1 scale | Fetch homepage + a few well-known paths (`/robots.txt`, `/sitemap.xml`, `/kontakt`, `/impressum`) only |
| Guessing exact revenue/headcount numbers | Precise-looking | Invented facts → violates AC5 | Tiers + ranges, labelled as assumptions |

## Feature Dependencies

```
HTTP fetch + URL normalization (dim 1)
    └──required by──> dims 2, 4, 5, 6 (all parse the same HTML)
    └──required by──> dim 3 PSI call (needs a reachable URL)
    └──required by──> Zahlungskräftigkeit signal group C (size from HTML)

PSI API call (dim 3 + dim 4 Lighthouse-SEO bonus)
    └──enhanced by──> PAGESPEED_API_KEY (quota for AC1 scale)
    └──degrades to──> viewport-meta heuristic when no key/network

Per-dimension verdicts ──required by──> 1–5 aggregation
dim 1 = dead ──overrides──> all other dimensions (score 5)

Name-suffix legal form (Zahlungskräftigkeit A)
    └──upgraded by──> Zefix lookup (assumption → confirmed fact)

JSON cache per URL ──required by──> AC7 (resumable) + AC8 (avoid duplicate API calls)
LLM layer ──enhances──> dim 6 + Begründung (optional, after deterministic checks)
```

## MVP Definition

### Launch With (v1) — satisfies AC1–AC11

- [ ] Excel/CSV in → Excel out, tolerant URL-column detection, 2 score columns + Begründung (AC2, AC9)
- [ ] URL normalization + reachability + parked/social detection = dim 1 with the score-5 override (AC4, AC11)
- [ ] HTTPS/SSL + free-subdomain detection = dim 2 (AC11)
- [ ] PSI call (perf + seo categories) with HTML viewport fallback = dim 3 (AC11, AC8)
- [ ] HTML-parse SEO signals = dim 4 (AC11)
- [ ] JSON-LD/OG = dim 5; contact/Impressum/freshness/generator = dim 6 (heuristic, AC11)
- [ ] Deterministic 1–5 aggregation with traceable reasons (AC3, AC6, AC11)
- [ ] Zahlungskräftigkeit A+B+C heuristic with logged assumptions, conservative default (AC5)
- [ ] Per-URL JSON cache + retry/backoff (AC7, AC8)
- [ ] Run on `data/sample_input.xlsx`, all 42 rows scored incl. 2 edge cases (AC10)

### Add After Validation (v1.x)

- [ ] PSI API key wiring + tuned thresholds — when keyless quota throttles at scale
- [ ] Zefix live lookup — when sales wants confirmed legal form / founding year
- [ ] LLM dim-6 qualitative layer — when richer Begründung is requested

### Future Consideration (v2+)

- [ ] Mobile screenshot capture — only if visual proof for sales becomes a real ask (heavy dep)
- [ ] Per-dimension breakout columns — if power users want fine-grained sorting

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| Dim 1 reachability + override | HIGH | LOW | P1 |
| Dim 2 HTTPS/SSL + free-subdomain | HIGH | LOW | P1 |
| Dim 4 SEO HTML parse | HIGH | LOW | P1 |
| Dim 3 PSI (perf+seo) + viewport fallback | HIGH | MEDIUM | P1 |
| Dim 5 JSON-LD/OG | MEDIUM | LOW | P1 |
| Dim 6 contact/Impressum/freshness/generator | MEDIUM | LOW | P1 |
| 1–5 aggregation + traceable reasons | HIGH | LOW | P1 |
| Zahlungskräftigkeit A+B+C heuristic | HIGH | LOW | P1 |
| Per-URL JSON cache + backoff | HIGH | LOW | P1 |
| PSI API key support | MEDIUM | LOW | P2 |
| Zefix lookup | MEDIUM | MEDIUM | P2 |
| LLM dim-6 layer | MEDIUM | MEDIUM | P2 |
| Screenshot capture | LOW | HIGH | P3 |

## Sources

- `docs/scoring_website_bedarf.md`, `CLAUDE.md`, `.planning/PROJECT.md` (project spec — HIGH)
- [Google PageSpeed Insights API v5 docs](https://developers.google.com/speed/docs/insights/v5/get-started) — response shape `lighthouseResult.categories.*.score`, `audits.*.numericValue`, `loadingExperience.metrics.*.category` (HIGH)
- [About PageSpeed Insights](https://developers.google.com/speed/docs/insights/v5/about) — CrUX field data being phased out of PSI; rely on Lighthouse lab scores (HIGH, drives the "CrUX = bonus only" recommendation)
- [DebugBear: PageSpeed Insights API](https://www.debugbear.com/blog/pagespeed-insights-api) — field reference corroboration (MEDIUM)
- [sitebuilderreport — free website builders](https://www.sitebuilderreport.com/free-website-builders) and [WebBuildersGuide free builders](https://www.webbuildersguide.com/best-website-builder/free/) — confirmed default subdomains wixsite.com / jimdosite.com / weebly.com / webnode.page (MEDIUM)
- Web standards (training, HIGH): Core Web Vitals thresholds LCP 2.5s/CLS 0.1/TBT 200ms; Swiss UWG Impressum expectation; Zefix as Switzerland's public central business index

---
*Feature research for: Swiss SME website lead-scoring CLI*
*Researched: 2026-06-14*
