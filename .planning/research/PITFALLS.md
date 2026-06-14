# Pitfalls Research

**Domain:** Local Python CLI scoring Swiss SME websites (Website-Bedarf 1–5 + Zahlungskräftigkeit 1–5) from a list, with live HTTP checks, optional PageSpeed Insights API + optional LLM, caching, graceful degradation
**Researched:** 2026-06-14
**Confidence:** HIGH (Python `requests`/openpyxl behavior, PSI API limits, LLM JSON failure modes are well-documented and stable; verified against project spec AC1–AC11)

This file maps every pitfall to the acceptance criteria it threatens. The single most important property of this tool is **AC1+AC4: process the whole list, never crash, every row gets a score.** Most critical pitfalls below are variations of "one bad row kills the run."

---

## Critical Pitfalls

### Pitfall 1: One unhandled error on a single row aborts the entire run

**What goes wrong:**
A run over 300 Swiss-SME rows crashes on row 47 because of a malformed URL (`htp://naehatelier-sutter` — literally in the sample data), a DNS failure, a connection reset, or an exception from a parser/LLM. All 46 already-fetched results are lost; the user sees a stack trace, not an output file.

**Why it happens:**
Developers wrap the happy path and let exceptions propagate. `requests`, `bs4`, `openpyxl`, JSON parsing, and SSL verification each raise *different* exception types, and it's easy to catch `requests.RequestException` but miss `ValueError`/`UnicodeError`/`ssl.SSLError`/`socket.timeout`/`MemoryError` from a 200 MB page.

**How to avoid:**
- Per-row `try/except Exception` boundary around all scoring work. A caught exception → fallback score (no website reachable ⇒ Bedarf 5) + a `Vermerk` noting the failure class. The loop *continues*.
- Inside that, narrower handlers per stage (fetch, parse, PSI, LLM) so the `Vermerk` is specific ("Timeout", "SSL-Fehler", "geparkt", "Social-only").
- Never let the row loop catch only `RequestException`. The outer net must be bare `Exception` (plus a comment why — normally an anti-pattern, here it's the AC4 guarantee).
- Write/flush output incrementally (see Pitfall 11) so a crash that *does* escape still leaves partial work.

**Warning signs:**
Any `except requests.X` without an outer catch-all; tests that only feed clean URLs; no test row with `htp://`, empty cell, or a known-timeout host.

**Phase to address:** Core fetch/scoring loop phase — this is the central robustness contract. Protects **AC1, AC4, AC7**.

---

### Pitfall 2: HTTP fetch hangs with no timeout, freezing the whole run

**What goes wrong:**
`requests.get(url)` with no `timeout` blocks indefinitely on a slow/dead Swiss host. Wall-clock for 300 rows becomes unbounded; the user kills the process and loses everything.

**Why it happens:**
`requests` has **no default timeout** — this is the single most common `requests` footgun. A connect that hangs or a server that dribbles bytes blocks forever.

**How to avoid:**
- Always pass `timeout=(connect, read)`, e.g. `timeout=(5, 10)`. Use a tuple so a slow-to-connect host fails fast separately from a slow-to-respond one.
- Cap total bytes read (stream + size limit, see Pitfall 5) so "200 OK but never ends" can't hang on the read side.
- Treat `Timeout` as a normal outcome → score it (likely high Bedarf, with `Vermerk` "Timeout"), don't retry forever.

**Warning signs:**
Any `requests.get`/`head` call without `timeout=`. A run that "sometimes takes 20 minutes."

**Phase to address:** Core fetch phase. Protects **AC1, AC4, AC8**.

---

### Pitfall 3: Default User-Agent gets 403'd; real sites scored as "no website"

**What goes wrong:**
Many Swiss SME sites sit behind WAFs/CDNs (Cloudflare, hosters) that block the literal `python-requests/2.x` User-Agent → 403. The tool concludes "not reachable ⇒ Bedarf 5" for a *perfectly good modern site*, inverting the score and corrupting the lead ranking.

**Why it happens:**
Developers forget to set headers. A 403 is a valid HTTP response (no exception), so it silently flows into the scoring logic as "bad site."

**How to avoid:**
- Set a realistic browser-like `User-Agent` (and `Accept-Language: de-CH,de;q=0.9`) on every request.
- Distinguish 403/406/429 ("blocked/limited — could not assess") from real connection failures and from "no website." A block must NOT be scored as Bedarf 5; mark `Vermerk` "blockiert – nicht bewertbar" and use a neutral/conservative score so it doesn't fake a top lead.
- Don't follow `HEAD`-only logic; some servers 405 on HEAD — fall back to GET.

**Warning signs:**
Many rows scoring Bedarf 5 with `Vermerk` "nicht erreichbar" for sites that load fine in a browser. Uniform 403s.

**Phase to address:** Core fetch phase, hardened during robustness pass. Protects **AC3, AC4, AC11** (Dimension 1 Existenz must not false-negative).

---

### Pitfall 4: http/https/www permutations cause false "not reachable"

**What goes wrong:**
Input cell is `example.ch` (no scheme) or `www.example.ch` or `http://example.ch` that 301s to `https://www....`. A naive fetch of the raw string fails or mis-evaluates SSL/redirect, and a live site is scored as dead. The spec explicitly says: before final verdict, check whether only scheme/`www` is missing.

**Why it happens:**
Real customer lists are messy — bare domains, trailing spaces, `http://`, mixed case. Developers test with clean `https://` URLs.

**How to avoid:**
- Normalize first: strip whitespace, lowercase host, prepend `https://` if no scheme.
- On failure, try a small permutation set: `https://`, `https://www.`, then `http://` as last resort. Record which one worked in `Vermerk`.
- Use `allow_redirects=True` but cap redirects (see Pitfall 6) and record the final URL (it feeds Dimension 2: own-domain vs free-subdomain).
- A successful redirect from http→https is a *positive* signal for Dimension 2, not a failure.

**Warning signs:**
Bare-domain rows all scoring Bedarf 5. `Vermerk` "nicht erreichbar" on domains that resolve.

**Phase to address:** Core fetch / URL-normalization phase. Protects **AC4, AC11** (Dim 1 & 2).

---

### Pitfall 5: Huge pages / streaming bodies exhaust memory or stall reads

**What goes wrong:**
A misconfigured site streams a multi-hundred-MB response or an endless body. `response.text` buffers it all → `MemoryError` or a multi-minute read, killing throughput.

**Why it happens:**
`requests` `.content`/`.text` reads the full body. Few developers cap response size.

**How to avoid:**
- `stream=True` + read with a byte cap (e.g. first ~2 MB is plenty for `<head>`, meta, schema, contact links). Abort beyond the cap.
- The Bedarf signals (title, meta, viewport, JSON-LD, OG, `tel:`/`mailto:`, impressum link) almost all live in the first chunk; full-page download is unnecessary.

**Warning signs:**
Occasional `MemoryError`; a single row taking minutes; RAM spikes.

**Phase to address:** Core fetch phase. Protects **AC1, AC4**.

---

### Pitfall 6: Infinite/long redirect loops and non-UTF8 encodings

**What goes wrong:**
(a) Redirect loops (`http`↔`https` misconfig, cookie walls) spin until `requests` raises `TooManyRedirects` — fine if caught, a crash if not.
(b) Swiss sites with `windows-1252`/`latin-1` or wrong/missing charset → `response.text` mojibake → German text (Impressum, Kontakt, ä/ö/ü) mis-detected → wrong Dimension-6 signals; or a `UnicodeDecodeError` on strict decode.

**Why it happens:**
`requests` guesses encoding from headers and can be wrong; `chardet`/`charset_normalizer` is a guess. Developers assume UTF-8.

**How to avoid:**
- Cap redirects (`requests` default is 30; set lower, e.g. `max_redirects` via Session, or rely on the `TooManyRedirects` catch).
- Decode defensively: prefer declared charset, fall back to `charset_normalizer`/`apparent_encoding`, and decode with `errors="replace"` so it never raises. Mojibake degrades a signal gracefully; a crash violates AC4.
- Match German keywords case-insensitively and accent-tolerantly (Impressum/Kontakt/Datenschutz).

**Warning signs:**
`TooManyRedirects` in logs; garbled `Vermerk` text; Impressum-present sites scored as missing it.

**Phase to address:** Core fetch + HTML-parse phase. Protects **AC4, AC11** (Dim 6).

---

### Pitfall 7: SSL/cert errors crash instead of becoming a *signal*

**What goes wrong:**
An expired/self-signed/hostname-mismatch cert raises `ssl.SSLError`/`SSLCertVerificationError`. If unhandled → crash. If handled by globally disabling verification → you lose the signal entirely. But a bad cert is *exactly* a Dimension-2 ("Technische Basis: gültiges SSL") finding — it should *raise* Bedarf, not crash and not be ignored.

**Why it happens:**
Two opposite over-reactions: let it crash, or `verify=False` everywhere to "make it work."

**How to avoid:**
- Catch SSL verification errors specifically. Record `Vermerk` "SSL ungültig/abgelaufen" → counts as a Dimension-2 lücke (higher Bedarf).
- Then optionally re-fetch with `verify=False` *only* to still read content for the other dimensions — but keep the SSL-fail signal. Never silently treat verify-off as "SSL ok."
- Suppress the `InsecureRequestWarning` noise only after the signal is captured.

**Warning signs:**
`SSLError` tracebacks; or conversely, no site ever flagged for SSL despite known bad-cert hosts.

**Phase to address:** Core fetch phase, tied to Dimension 2 scoring. Protects **AC4, AC11** (Dim 2), **AC3**.

---

### Pitfall 8: PageSpeed Insights turns a 300-row run into hours / 429s and blocks the whole run

**What goes wrong:**
PSI calls take ~10–30 s each and the **keyless** quota is tiny. 300 rows × 20 s sequential = ~100 min; keyless quota exhausts after a handful of calls → 429s. If PSI is a hard dependency in the loop, the run stalls or aborts — directly violating AC1/AC8. Worse, a PSI failure scored as "bad performance" inverts the score.

**Why it happens:**
Treating the optional PSI/Dimensions 3–4 as mandatory and inline. Underestimating keyless limits (very low/day) and per-call latency.

**How to avoid:**
- Make PSI strictly **optional and skippable** — a CLI flag/`.env` (`PAGESPEED_API_KEY`). Without a key, either skip Dim 3–4 (heuristic fallback: viewport-meta presence for mobile) or use the low keyless rate with a hard call budget.
- Never block the run on PSI: it runs *after* the deterministic checks; its absence degrades to a `Vermerk` "PageSpeed übersprungen", not a low score.
- Batching/backoff (AC8): bounded concurrency, exponential backoff on 429/5xx with jitter, a max-retry cap, and a per-run PSI call budget. Cache every PSI result (Pitfall 10).
- A PSI error/timeout ≠ "slow site." Mark "nicht gemessen", don't penalize Dimension 3.

**Warning signs:**
Runs that take hours; bursts of 429; Bedarf scores swinging when PSI is on vs off; no `--no-pagespeed` escape hatch.

**Phase to address:** Dedicated PSI-integration phase (after core scoring works without it). Protects **AC1, AC4, AC8, AC11** (Dim 3–4).

---

### Pitfall 9: Inverted / off-by-one / non-integer / empty scores

**What goes wrong:**
AC3 demands "higher = more need / more purchasing power." Easy to invert: a *modern* site accidentally scores 5 (it should be 1), so the worst leads sort to the top. Or scores come out as floats (`3.5`), strings, `None`, or out of range — AC2 forbids empty/non-integer scores. Or the "no reachable website ⇒ Bedarf 5" override loses to a later partial signal and lands at 2.

**Why it happens:**
Mixing "good = high" (purchasing power) and "bad = high" (need) in the same code invites sign errors. Aggregating six dimensions into 1–5 with floats and forgetting to clamp/round. Override applied before other signals overwrite it.

**How to avoid:**
- A single, tested mapping function per score with explicit direction and a docstring. Golden tests: empty URL → Bedarf 5; modern reference site → Bedarf 1; AG with many sites → Zahlungskräftigkeit high.
- Always `int(round(...))` then **clamp to [1,5]**. Assert the result is an int in 1–5 before writing — a row that can't be scored gets the documented fallback, never empty/None.
- Apply the "no website ⇒ 5" as a *final* override that cannot be downgraded.
- Direction regression test: a fixture set with known-good and known-bad sites asserting ordering.

**Warning signs:**
Modern sites at the top of the Bedarf ranking; floats/strings/blanks in the score columns; `KeyError`/`None` reaching the writer.

**Phase to address:** Scoring-aggregation phase + a dedicated scoring-tests step. Protects **AC2, AC3, AC11**.

---

### Pitfall 10: Sorting the output drops or scrambles rows

**What goes wrong:**
Spec: output sorted by Bedarf desc, then Zahlungskräftigkeit desc, **without losing original rows**. A buggy sort (sorting only the score columns, not whole records; dropping rows with NaN/None scores; or sorting in-place over a partially written sheet) loses customers from the output — silently failing AC1/AC2.

**Why it happens:**
Sorting columns independently instead of whole row objects; pandas-style NaN handling; treating header row as data.

**How to avoid:**
- Build a list of complete row records (all original columns + 2 scores + `Vermerk`), then `sorted(rows, key=lambda r: (-bedarf, -zahlung))`. Re-emit *every* record.
- Assert `len(output_rows) == len(input_rows)` before writing. This single assertion catches most drop bugs.
- Keep an original-order tiebreaker so equal scores stay stable.

**Warning signs:**
Output has fewer rows than input; specific customers missing; header treated as a data row.

**Phase to address:** Output/sort phase. Protects **AC1, AC2**.

---

### Pitfall 11: Cache corruption / partial writes on abort destroy resumability

**What goes wrong:**
AC7 says an abort must not discard all work. If the cache is one big JSON written at the end, Ctrl-C loses everything. If a per-URL cache file is written non-atomically and the process dies mid-write, the file is truncated/invalid JSON → next run crashes reading it (re-introducing Pitfall 1).

**Why it happens:**
Writing cache at process exit; `open(...,'w')` + dump interrupted mid-stream leaves a half-file; no atomic replace.

**How to avoid:**
- Cache **per URL** (one entry/file keyed by normalized URL), written incrementally as each row completes — so an abort at row 200 keeps 199 results.
- Atomic writes: write to a temp file then `os.replace()`. Reads of a corrupt/missing cache entry must be caught and treated as "not cached" (re-fetch), never crash.
- Also flush the *output* incrementally or at least write a partial output on interrupt, so a long run yields usable results even if not fully finished.

**Warning signs:**
Re-running after Ctrl-C re-does all work; JSON decode errors reading cache; zero-byte cache files.

**Phase to address:** Caching/resumability phase. Protects **AC7, AC8, AC1**.

---

### Pitfall 12: Stale cache and cache-key collisions give wrong/mixed results

**What goes wrong:**
(a) A site that changed (now has HTTPS, now mobile) keeps its old low/high score forever — stale cache → wrong leads. (b) Key collisions: `example.ch` and `www.example.ch` and `https://example.ch/` hash to different keys (duplicate work) *or* unrelated URLs collide (wrong data served).

**Why it happens:**
Caching the raw input string instead of the normalized URL; no schema/version in cache entries; no TTL or invalidation story.

**How to avoid:**
- Key on the **normalized** URL (same normalization as fetch). Document that there's no auto-TTL (this is a one-shot batch tool) but provide a `--no-cache`/clear-cache flag for a fresh run.
- Stamp each cache entry with a scoring-logic version; bump it when the algorithm changes so old entries are ignored.
- Store enough raw signals in the cache (not just the final score) so re-scoring after a logic change doesn't require re-fetching.

**Warning signs:**
Scores don't change after fixing the algorithm; same site fetched twice; suspicious identical scores across unrelated rows.

**Phase to address:** Caching phase. Protects **AC7, AC3**.

---

### Pitfall 13: Excel I/O alters or drops original columns / types

**What goes wrong:**
AC2: original columns must pass through **unchanged**. Common damage: leading zeros in Kundennummer/PLZ stripped (`8001` ok but `0123`→`123`), phone/IDs turned to floats/scientific notation, dates reformatted, empty cells turned to the string `"None"`, number formats and the original column order lost, or a header row mis-handled.

**Why it happens:**
Round-tripping through pandas/`str()` coercion; rebuilding the sheet instead of appending columns; reading `cell.value` and re-stringifying.

**How to avoid:**
- With openpyxl, **append two columns to the existing sheet** rather than reconstructing it — preserves original cell values, types, and order by construction.
- Preserve cell values as-is; only write the two new score cells (+ optional `Vermerk`) as integers/text. Don't coerce Kundennummer/PLZ to int.
- For CSV, read everything as text; don't let a CSV reader infer numeric types.
- Round-trip test: read sample, write output, assert original columns byte-equal (values + order) for all 42 sample rows.

**Warning signs:**
Leading zeros gone; phone numbers in `1.23E+10`; `"None"`/`"nan"` strings in cells; column reordering; the two Edge-Case rows (empty/broken URL) corrupted.

**Phase to address:** Excel-I/O phase (early — it's the input/output boundary). Protects **AC2, AC9, AC10**.

---

### Pitfall 14: URL-column detection fails on header variants / empty cells

**What goes wrong:**
Spec requires tolerant detection of "URL"/"Website"/"Webseite"/"Web"/etc., and a clear error if none found. Failure modes: hard-coding `"URL"` (sample uses `"Website"`); case/whitespace mismatch (`" Website "`, `"WEBSITE"`); picking the wrong column when several match; crashing on an empty URL cell instead of scoring it Bedarf 5 with `Vermerk` "keine Website".

**Why it happens:**
Exact-string column lookup; assuming the column is always present and always populated.

**How to avoid:**
- Case-insensitive, trimmed matching against a synonym list (`url, website, webseite, web, homepage, internet`). If multiple match, pick the most URL-like by sampling cell values; log which column was chosen.
- If none match → clear, actionable error message naming the columns found (fail fast here is correct; this is setup, not a data row).
- Empty/whitespace URL cell → not an error: Bedarf 5, `Vermerk` "keine Website" (matches the sample Kiosk edge case).

**Warning signs:**
"No URL column" on the sample file; only `"URL"` header works; crash on the empty-URL Kiosk row.

**Phase to address:** Excel-I/O / input-parsing phase. Protects **AC2, AC4, AC9, AC10**.

---

### Pitfall 15: Zahlungskräftigkeit hallucinated as fact (esp. via LLM)

**What goes wrong:**
AC5: purchasing power must be a **documented estimate from public sources, no invented facts**. With an LLM in the loop, the model confidently fabricates revenue, headcount, founding year, or Zefix entries. Even heuristically, one over-trusted signal (e.g. ".ch domain ⇒ big company") produces confident-but-wrong scores and the `Vermerk` claims a source that doesn't exist.

**Why it happens:**
LLMs fill gaps with plausible numbers; developers print the LLM's claimed "source" verbatim. Heuristics get treated as ground truth.

**How to avoid:**
- The Zahlungskräftigkeit `Vermerk` must state it's a *Schätzung* and which **observable** signals drove it (legal form from name, branch, multi-location/team-page signals on the site, optional Zefix). Never assert a number the tool didn't actually retrieve.
- If LLM used: constrain it to *infer a 1–5 estimate from provided observable features*, not to recall facts; forbid inventing figures; require it to label confidence. Prefer deterministic heuristics as the base, LLM as an optional refiner.
- When data is thin → score conservatively (toward the middle/low) and mark "geschätzt, geringe Datenlage" (spec: "konservativ schätzen und kennzeichnen").

**Warning signs:**
`Vermerk` cites specific revenue/employee numbers; identical "sources" across rows; Zahlungskräftigkeit 5 for obvious micro-firms.

**Phase to address:** Zahlungskräftigkeit-scoring phase (+ LLM-integration phase if used). Protects **AC5, AC6**.

---

### Pitfall 16: Legal-form heuristics misfire on Swiss names

**What goes wrong:**
Deriving purchasing power from legal form in the firm name (AG/GmbH/Einzelfirma) misfires: "Müller AG" might be a tiny shell; "Dr. med. dent. X" (Zahnarzt) is a high-earner Einzelfirma; substring matching flags "Sagi" or names containing "ag"/"gmbh" as tokens. Branch effects (Treuhand/Zahnarzt/Immobilien high; Coiffeur/Kiosk low) get ignored or applied crudely.

**Why it happens:**
Naive substring `"ag" in name`; treating legal form as the only signal; ignoring branch (the sample is branch-rich: Maler, Schreiner, Garage, Zahnarzt, Treuhand, Coiffeur, Velo, Immobilien…).

**How to avoid:**
- Token/regex match legal-form suffixes word-bounded and case-insensitive (`\bAG\b`, `\bGmbH\b`, Sàrl/SA for Romandie), not substring.
- Combine **legal form + branch + website-derived size signals** (multiple locations, team page, online shop) into the estimate; document weights.
- Keep a branch→baseline table that's transparent and editable, with a `Vermerk` showing which factors applied.

**Warning signs:**
Every "...ag..." name scored high; Zahnarzt/Treuhand scored low; pure-legal-form scores ignoring branch.

**Phase to address:** Zahlungskräftigkeit-scoring phase. Protects **AC5, AC3, AC6**.

---

### Pitfall 17: LLM nondeterminism, JSON-parse failures, missing keys

**What goes wrong:**
If an LLM layer is used: (a) it returns prose around the JSON or markdown fences → `json.loads` throws → row crashes (Pitfall 1) or silently drops a signal; (b) nondeterministic scores make runs non-repeatable (tension with AC7's "wiederholbar"); (c) `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` absent → code assumes it's there and crashes at import/first call; (d) per-call cost/rate limits on hundreds of rows.

**Why it happens:**
Trusting the model to emit clean JSON; no key-presence guard; no caching of LLM output; calling the LLM for every row regardless of need.

**How to avoid:**
- LLM strictly optional: detect key presence at startup; absent ⇒ skip LLM layer with a `Vermerk`, deterministic heuristics still produce a full score (graceful degradation per Constraints).
- Robust JSON extraction (regex out the first `{...}`, tolerate fences) wrapped in try/except → on failure, fall back to heuristic, never crash.
- Set `temperature=0`/low for repeatability; cache LLM output per URL (Pitfall 11/12) so re-runs are stable and cheap.
- Rate/cost control: batching + backoff (AC8), a per-run LLM budget, and only invoke the LLM where it adds value (e.g. Dimension 6 qualitative), not for things heuristics already cover.

**Warning signs:**
`JSONDecodeError`; scores differ between identical runs; crash when keys unset; surprising API bills; LLM called on every row.

**Phase to address:** LLM-integration phase (last, additive). Protects **AC4, AC7, AC8** (and AC5 via Pitfall 15).

---

### Pitfall 18: Committing `.env` or output files; scope creep beyond a CLI

**What goes wrong:**
API keys (PageSpeed/Anthropic/OpenAI) committed via `.env`; output Excel with scraped customer/company data committed — both violate §6 (lokal arbeiten, nichts committen, keine Veröffentlichung von Firmendaten). Separately, scope creep: someone adds a web dashboard, a daemon, scheduled runs, or a DB — explicitly out of scope.

**Why it happens:**
`.gitignore` missing entries; `git add .` sweeping up `output/` and `.env`; "wouldn't a little web UI be nice."

**How to avoid:**
- `.gitignore` must cover `.env`, `output/`, cache dir, and any scraped-data artifacts from the start; verify with `git status` before any commit.
- Load secrets only from `.env`/env vars; never hard-code or log full keys.
- Keep the deliverable a single CLI entrypoint (file in → file out, AC9). Treat any dashboard/daemon/CRM-integration request as out-of-scope (Out of Scope list).

**Warning signs:**
`.env` or `output/*.xlsx` appearing in `git status`; keys in code/logs; tickets proposing a UI or scheduler.

**Phase to address:** Setup/scaffolding phase (gitignore + .env) and every phase boundary (scope guard). Protects **§6, AC9**.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| No `timeout` on requests | Less code | Run hangs forever on one dead host (AC1/AC4 fail) | **Never** |
| Catch only `requests` exceptions | Looks clean | Non-HTTP errors crash the run | **Never** — outer catch-all is mandatory |
| Skip per-URL cache, write at end | Simpler | Ctrl-C loses all work (AC7 fail) | Only a throwaway <10-row spike |
| Hard-code URL column name | Fast first run | Breaks on real lists / sample uses "Website" | MVP day-1 only, fix before AC10 |
| Make PSI a hard dependency | Single code path | Run takes hours / 429-aborts (AC8 fail) | **Never** — must be skippable |
| LLM for every row, no cache | Best qualitative scores | Cost + nondeterminism + rate limits | Only if budget-capped and cached |
| `verify=False` globally | "It just works" | Loses Dim-2 SSL signal, masks real failures | **Never** — capture signal first |
| Store only final score in cache | Smaller cache | Re-score after logic change needs re-fetch | Acceptable; store raw signals if cheap |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `requests` (HTTP) | No timeout, default UA, no size cap, `.text` on huge body | `timeout=(5,10)`, browser UA + `de-CH`, `stream=True` + byte cap, decode `errors="replace"` |
| PageSpeed Insights | Keyless inline + mandatory; treat error as "slow" | Optional w/ key, post-pass, budgeted, backoff on 429, cache, error ≠ low score |
| openpyxl | Rebuild sheet / coerce types → lose leading zeros, formats | Append 2 columns to existing sheet, preserve original cells untouched |
| Zefix / public company data | Assume structured API; scrape & assert facts | Use only as optional source; record as estimate; conservative fallback |
| LLM API | Assume clean JSON, assume key present, temp default | Key-presence guard, robust JSON extraction, temp=0, cache, budget |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential PSI calls | Run takes hours | Bounded concurrency + budget, or skip without key | ~50+ rows |
| No caching across re-runs | Every re-run re-fetches everything | Per-URL atomic cache | Any 2nd run / any abort |
| Unbounded body download | RAM spikes, slow rows | `stream=True` + byte cap | Any oversized/streaming site |
| Unbounded retries/backoff | Run never finishes on flaky hosts | Max-retry cap + jittered backoff | Clusters of 429/5xx |
| LLM on every row | Slow + costly | Cache + selective invocation | Hundreds of rows |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Commit `.env` with API keys | Key leak / abuse / cost | `.gitignore` `.env`, load from env only, never log keys |
| Commit scraped customer/company data | Privacy breach (§6) | `.gitignore` `output/` + cache; keep data local |
| Log full URLs + LLM responses with PII | Sensitive data in logs | Log signals/scores, not raw scraped personal data |
| `verify=False` everywhere | MITM exposure + lost SSL signal | Verify by default; disable only post-signal, scoped per request |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress / silent long run | User thinks it hung, kills it (loses work) | Per-row progress + ETA; incremental output |
| Cryptic crash instead of output | Sales gets nothing from a 300-row list | Per-row fallback score + `Vermerk`; always produce a file |
| Score columns without reasons | Can't trust/explain a lead (AC6) | `Vermerk` column with driving signals + run log |
| README needs >5 min to run | Tool unused | One command, `.env.example`, keyless default path (AC9) |
| Best leads not on top | Sales scrolls/misses (defeats core value) | Default sort Bedarf desc, then Zahlung desc; verify ordering |

## "Looks Done But Isn't" Checklist

- [ ] **Robustness:** Run the *full* sample including the empty-URL Kiosk and `htp://naehatelier-sutter` rows — verify no crash and both get a score + `Vermerk` (AC4, AC10).
- [ ] **Every row scored:** `len(output) == len(input)`; zero empty/non-integer scores; all in 1–5 (AC1, AC2).
- [ ] **Score direction:** Modern reference site → Bedarf 1; no/dead site → Bedarf 5; ordering test passes (AC3).
- [ ] **Override wins:** "no reachable website ⇒ Bedarf 5" cannot be downgraded by a later partial signal (AC4, AC11).
- [ ] **Column passthrough:** Original columns + types (leading zeros, formats) byte-identical in output (AC2).
- [ ] **URL-column variants:** Detection works for Website/Webseite/Web/URL and errors clearly if none (AC2, AC9).
- [ ] **PSI skippable:** Tool runs fully without `PAGESPEED_API_KEY` (heuristic Dim 3–4) and without hanging (AC8).
- [ ] **Resumability:** Ctrl-C mid-run, re-run → cached rows skipped, no cache-read crash (AC7).
- [ ] **Estimate honesty:** Zahlungskräftigkeit `Vermerk` says "Schätzung" + lists real signals; no invented numbers (AC5, AC6).
- [ ] **LLM-off path:** Runs with no API keys at all, full scores via heuristics (Constraints, AC4).
- [ ] **Privacy:** `git status` shows no `.env`, no `output/`, no cache (§6).
- [ ] **Sort:** Best leads (high Bedarf + high Zahlung) on top; no rows lost in sort (AC1, AC2).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Run crashed mid-list (Pitfall 1/2) | LOW (if cache exists) | Fix the bug; re-run; per-URL cache skips done rows |
| Inverted/off-by-one scores (Pitfall 9) | LOW–MED | Fix mapping fn; bump cache logic-version; re-score from cached signals (no re-fetch) |
| PSI quota blew up (Pitfall 8) | LOW | Add key or `--no-pagespeed`; cached non-PSI work intact |
| Corrupt cache file (Pitfall 11) | LOW | Reads catch + treat as miss; delete bad entry; re-fetch that URL |
| Original columns mangled (Pitfall 13) | MED | Switch to append-columns approach; re-run from input (cache speeds it) |
| LLM hallucinated facts (Pitfall 15) | MED | Remove fabricated `Vermerk`; constrain prompt to inference-only; re-run LLM layer |
| `.env`/output committed (Pitfall 18) | HIGH | Rotate leaked keys; `git rm --cached` + history scrub; fix `.gitignore` |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 One-row crash aborts run | Core fetch/scoring loop | Full sample incl. broken/empty URL → no crash, file produced |
| 2 No timeout / hang | Core fetch | No request without `timeout=`; dead-host fixture fails fast |
| 3 403 / default UA | Core fetch (robustness) | Block ≠ Bedarf 5; UA header set |
| 4 http/https/www permutations | Core fetch / normalization | Bare-domain fixtures score correctly |
| 5 Huge pages | Core fetch | Byte cap enforced; oversized fixture handled |
| 6 Redirect loops / encoding | Core fetch + HTML parse | `TooManyRedirects` caught; latin-1 fixture decodes |
| 7 SSL errors | Core fetch (Dim 2) | Bad-cert fixture → signal, no crash |
| 8 PSI quota/latency | PSI-integration phase | Runs without key; backoff on 429; budget honored |
| 9 Inverted/off-by-one/empty scores | Scoring-aggregation + tests | Golden direction tests; all scores int 1–5 |
| 10 Sort drops rows | Output/sort | `len(output)==len(input)` assertion |
| 11 Cache corruption / partial write | Caching/resumability | Ctrl-C test; atomic write; corrupt-entry test |
| 12 Stale cache / key collision | Caching | Normalized key; logic-version stamp; `--no-cache` flag |
| 13 Excel column/type loss | Excel-I/O (early) | Round-trip byte-equal original columns |
| 14 URL-column detection | Excel-I/O / input parse | Header-variant + empty-cell fixtures |
| 15 Hallucinated company facts | Zahlungskräftigkeit (+LLM) | `Vermerk` = estimate, real signals only |
| 16 Legal-form heuristic misfire | Zahlungskräftigkeit | Word-bounded match; branch+size combined |
| 17 LLM JSON/key/nondeterminism | LLM-integration (last) | No-key path; JSON-fail fallback; temp=0 + cache |
| 18 `.env`/output commit, scope creep | Setup + every phase boundary | `git status` clean; deliverable stays a CLI |

## Sources

- Python `requests` documentation — default no-timeout behavior, `stream`, redirects, SSL verification, `Session.max_redirects` (HIGH; official docs, stable).
- Google PageSpeed Insights API documentation — per-call latency, keyless vs keyed quota, 429 behavior (HIGH; official docs).
- openpyxl documentation — appending columns to existing worksheets, cell value/type preservation (HIGH; official docs).
- LLM JSON-mode / structured-output failure modes — fenced output, key-absence, nondeterminism, temperature (HIGH; common, well-documented across Anthropic/OpenAI docs).
- Project spec `CLAUDE.md` (AC1–AC11, §6), `docs/scoring_website_bedarf.md` (6 dimensions + edge cases), `.planning/PROJECT.md` (constraints, sample data, key decisions) — authoritative project source of truth.

---
*Pitfalls research for: local Python CLI scoring Swiss SME websites (Website-Bedarf + Zahlungskräftigkeit)*
*Researched: 2026-06-14*
