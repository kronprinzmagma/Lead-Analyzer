# Phase 8: Company Research (Zefix) for Zahlungskräftigkeit — Research

**Researched:** 2026-06-15
**Domain:** Swiss Commercial Register REST API integration — optional, gated, cache-aside client mirroring pagespeed.py
**Confidence:** HIGH (API contract verified from official OpenAPI spec; code patterns verified from existing codebase)

---

## Summary

Phase 8 activates DIFF-01: authoritative legal-form and status data from the Swiss Federal Commercial Register (Zefix) replaces the name-string guess in payment Group A. The implementation follows the exact pattern established by `clients/pagespeed.py` — a gated, optional client that returns `None` on every error and degrades cleanly to the offline heuristic when credentials are absent or a lookup fails. Without `ZEFIX_USER` / `ZEFIX_PASSWORD` in the environment the run is byte-identical to today's Phase 7 baseline.

The Zefix REST API is a public-sector API (Federal Office of Justice) requiring HTTP Basic Auth obtained by emailing zefix@bj.admin.ch. The API has a documented rate-limit concern (third-party wrappers enforce a minimum 1 s inter-request interval); no official rate-limit header documentation was found, so the implementation must be conservatively throttled with the same `_Budget` + `Semaphore` + backoff pattern already used for PageSpeed. The API does NOT return share capital or employee count in the search response (those fields exist only on the `CompanyFull` response from a UID lookup, which would cost a second request); for this phase, capital/size stay as the current HTML/heuristic ("unknown").

The phase scope is narrow: one new file (`lead_analyzer/clients/zefix.py`), one new dataclass (`ZefixFacts` in `models.py`), two Config fields (`use_zefix`, `zefix_concurrency`), and surgical edits to `payment.estimate()` and `pipeline.run()`. No existing behavior changes when Zefix is OFF.

**Primary recommendation:** Build `ZefixClient` as a near-identical twin of `PageSpeedClient`. Single POST to `/api/v1/company/search`, parse `legalForm.shortName.de` + `status` from the first (and only) unambiguous hit, cache under `zefix-v1` namespace, degrade to `None` on every error including ambiguous matches.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIFF-01 | Live-Zefix-Lookup for Zahlungskräftigkeit — authoritative legal form + status + seat replaces name-heuristic; gated on ZEFIX_USER/ZEFIX_PASSWORD (byte-identical without creds) | §Zefix API Contract, §Wiring, §Score Composition |
| ZK-01 | Zahlungskräftigkeit score from public signals including legal form | Zefix provides authoritative legalForm replacing Group A name-guess |
| ZK-02 | Schätzung marked as such, signals/assumptions traceable, no invented facts | ZefixFacts.source field ("zefix" / "heuristik" / "nicht-gefunden") + "nicht gefunden" on ambiguous match |
| NACH-01 | Signals visible in Begründungsspalte and/or run-log | ZefixFacts flows through PaymentEstimate.signals, same JSONL run-log path |
| PERF-02 | External APIs use batching/retry/backoff; API error never aborts run | _Budget + Semaphore + Retry-After backoff; lookup() never raises |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Zefix API call | API/Backend (CLI pipeline) | — | CLI script, no frontend tier; network I/O lives in clients/ layer |
| Company name matching | API/Backend (clients/zefix.py) | — | Conservative heuristic inside ZefixClient.lookup() |
| Score composition (legal form + status) | API/Backend (analyzers/payment.py) | — | Offline analyzer receives ZefixFacts, applies scoring logic |
| Caching (zefix-v1 namespace) | Storage (cache.py) | — | Existing cache module, new namespace key |
| Config / credential gating | API/Backend (config.py + pipeline.py) | — | Mirrors pagespeed gating pattern exactly |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | already installed | HTTP POST to Zefix API with Basic Auth | Already in project; pagespeed.py uses it; no new dep |
| `threading` | stdlib | Semaphore + _Budget (same as pagespeed.py) | stdlib; already used |
| `base64` | stdlib | Basic Auth header encoding (standard HTTP) | stdlib; no dep |
| `cache` (project module) | — | zefix-v1 namespace, negative-hit caching | Already exists; just use a new key prefix |

**No new pip dependencies required.** [VERIFIED: existing requirements in project; requests already present]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GET /company/uid/{id} (two-step) | POST /company/search only | Two-step gives `CompanyFull` with capital data, but adds a second network call per row and the capital data is a string (not structured), not worth the extra cost for a score modifier |
| `httpx` | `requests` | httpx is not installed; requests already present |

---

## Zefix API Contract (VERIFIED)

**Source:** Official OpenAPI spec extracted from `spec/zefix.json` in [TenderLift/zefix-client](https://github.com/TenderLift/zefix-client) — this is a generated client from the official Zefix OpenAPI spec v2.7.2.3.
[VERIFIED: github.com/TenderLift/zefix-client/blob/main/spec/zefix.json]
[VERIFIED: github.com/validitylabs/zefix/blob/main/src/search.ts — request shape]
[VERIFIED: github.com/jschwendener/zefix-php/blob/main/src/DTO/Company.php — response field names]

### Base URLs

| Environment | Base URL |
|-------------|----------|
| PRODUCTION | `https://www.zefix.admin.ch/ZefixPublicREST/api/v1` |
| TEST/INTG | `https://www.zefixintg.admin.ch/ZefixPublicREST/api/v1` |

### Authentication

HTTP Basic Auth — `Authorization: Basic base64(username:password)` on every request.

```python
import base64
token = base64.b64encode(f"{user}:{password}".encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
```

Credentials obtained by emailing zefix@bj.admin.ch; the email address becomes the username.
[VERIFIED: github.com/jschwendener/zefix-php README + Bruno collection auth:basic]

### Primary Endpoint: POST /api/v1/company/search

**Request body schema** (`CompanySearchQuery`):

```json
{
  "name": "Muster AG",
  "canton": "ZH",
  "activeOnly": false
}
```

Required fields: `name` (string, minLength 3). Optional: `canton` (2-char abbreviation), `activeOnly` (boolean), `legalFormId`, `legalFormUid`, `registryOfCommerceId`, `legalSeatId`.

**Wildcard:** `*` is supported as a wildcard character in the name field (Zefix-style prefix search).

**Response:** HTTP 200 → JSON array of `CompanyShort` objects (0..N elements).

### CompanyShort Response Schema (from POST /company/search)

```json
[
  {
    "name": "Muster AG",
    "ehraid": 12345678,
    "uid": "CHE-123.456.789",
    "chid": "CH-400.1.234.567-8",
    "legalSeatId": 261,
    "legalSeat": "Zürich",
    "registryOfCommerceId": 20,
    "legalForm": {
      "id": 3,
      "uid": "0106",
      "name": {"de": "Aktiengesellschaft", "fr": "Société anonyme", "it": "Società anonima", "en": "Corporation"},
      "shortName": {"de": "AG", "fr": "SA", "it": "SA", "en": "Ltd"}
    },
    "status": "ACTIVE",
    "sogcDate": "2023-04-15",
    "deletionDate": null
  }
]
```

**Status enum values (exhaustive):**
- `"ACTIVE"` — company is active
- `"CANCELLED"` — deleted from the register
- `"BEING_CANCELLED"` — in liquidation process

**Parse paths for the implementation:**

| Field needed | JSON path | Notes |
|---|---|---|
| Legal form short name (DE) | `result["legalForm"]["shortName"]["de"]` | "AG", "GmbH", "KlG", etc. |
| Legal form short name (FR) | `result["legalForm"]["shortName"]["fr"]` | "SA", "Sàrl" for Romandie |
| Legal form full name (DE) | `result["legalForm"]["name"]["de"]` | Fallback for unknown abbreviations |
| Legal form internal ID | `result["legalForm"]["id"]` | int; use as sanity check |
| Status | `result["status"]` | "ACTIVE" / "CANCELLED" / "BEING_CANCELLED" |
| Canton | `result["legalSeat"]` | Name of commune, NOT canton abbrev (note: canton abbrev only in CompanyFull) |
| UID (for source URL) | `result["uid"]` | "CHE-..." format |
| Zefix detail URL | Not in CompanyShort | Only in CompanyFull — construct manually: `https://www.zefix.admin.ch/de/search/entity/{ehraid}/info` using `result["ehraid"]` |

**Result count semantics:**
- `len(results) == 0` → zero match → "nicht gefunden", fall back to heuristic
- `len(results) == 1` → unambiguous → use `results[0]`
- `len(results) > 1` → ambiguous → "nicht gefunden", fall back to heuristic (AC5: no wrong attribution)

**Note on `canton` field:** The `CompanyShort` response returns `legalSeat` (commune name) and `legalSeatId` but NOT the 2-char canton abbreviation. The canton abbreviation appears only in `CompanyFull` (GET /company/uid/{id}). For this phase, use `legalSeat` (commune name) as the seat info in signals. [VERIFIED: OpenAPI CompanyShort schema — no `canton` field; CompanyFull schema — has `canton`]

**Note on capitalNominal:** NOT present in `CompanyShort`. Only in `CompanyFull` (second GET call). Capital/employees stay heuristic/"unknown" per AC5. [VERIFIED: OpenAPI CompanyShort schema — no capitalNominal field]

### Error Responses

HTTP 400, 404, 500 → JSON `{"error": {"type": "...", "message": "..."}}`.
Error type `RESULTLIST_TO_LARGE` can appear (not a typo in spec — it's `TO_LARGE`, not `TOO_LARGE`). All non-200 → degrade to None.
[VERIFIED: ErrorDetails schema from OpenAPI spec]

---

## Architecture Patterns

### System Architecture Diagram

```
pipeline.run()
    │
    ├─ ZefixClient.from_config(config)          ← built ONCE, shared across all workers
    │      │
    │      └─ None if ZEFIX_USER/ZEFIX_PASSWORD absent → offline-identical run
    │
    └─ ThreadPoolExecutor → analyze_row(record, url_col, config, ps_client, zx_client)
           │
           ├─ fetch / soup / verdicts (unchanged)
           │
           └─ payment.estimate(record, fr, soup, config, zefix_facts=None)
                  │
                  ├─ ZefixClient.lookup(name) → ZefixFacts | None
                  │      ├─ cache.get("zefix-v1", name_key) → hit → return cached
                  │      ├─ _Budget.try_consume() → False → return None
                  │      ├─ _request(name, canton_hint) → POST /company/search
                  │      │      ├─ 200, len==1 → ZefixFacts(legal_form, status, uid, source="zefix")
                  │      │      ├─ 200, len==0 or len>1 → None (negative-hit cached)
                  │      │      ├─ non-200 / timeout → None (NOT cached)
                  │      │      └─ 429 → retry with backoff (max 3 attempts), then None
                  │      └─ cache.put("zefix-v1", name_key, payload | {"_miss": True})
                  │
                  ├─ Group A (legal form): ZefixFacts.legal_form if available, else name-heuristic
                  ├─ Group B (branch tier): unchanged
                  └─ Group C (HTML size signals): unchanged
```

### Recommended Project Structure

```
lead_analyzer/
├── clients/
│   ├── pagespeed.py      # existing — mirror this exactly
│   └── zefix.py          # NEW — ZefixClient (this phase)
├── analyzers/
│   └── payment.py        # EDIT — accept optional zefix_facts param
├── models.py             # EDIT — add ZefixFacts dataclass
├── config.py             # EDIT — add use_zefix, zefix_concurrency, zefix_budget fields
└── pipeline.py           # EDIT — build ZefixClient once, thread through analyze_row
tests/
└── test_zefix_client.py  # NEW — mirrors test_pagespeed_client.py structure
```

### Pattern 1: ZefixClient (mirrors PageSpeedClient exactly)

```python
# Source: mirrors lead_analyzer/clients/pagespeed.py structure
# [VERIFIED: pagespeed.py full read above]

class ZefixClient:
    def __init__(self, user, password, semaphore, budget, timeout, sleep=time.sleep):
        self._auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._sem = semaphore
        self._budget = budget
        self._timeout = timeout
        self._sleep = sleep   # injected for tests (no-op)

    @classmethod
    def from_config(cls, config) -> "ZefixClient | None":
        if not getattr(config, "use_zefix", False):
            return None
        user = os.environ.get("ZEFIX_USER")
        password = os.environ.get("ZEFIX_PASSWORD")
        if not user or not password:
            return None
        return cls(
            user, password,
            threading.Semaphore(getattr(config, "zefix_concurrency", 2)),
            _Budget(getattr(config, "zefix_budget", 200)),
            (config.timeout_connect, max(config.timeout_read, 15.0)),
        )

    def is_available(self) -> bool:
        return self._auth is not None and not self._budget.exhausted()

    def lookup(self, name: str, canton: str | None = None) -> "ZefixFacts | None":
        # Cache key includes canton to avoid false hits across cantons
        ck = cache.key_for(["zefix-v1", name, canton or ""])
        cached = cache.get(ck)
        if cached is not None:
            # Negative hit: {"_miss": True} was stored → return None
            if cached.get("_miss"):
                return None
            return ZefixFacts(**cached)
        if not self._budget.try_consume():
            return None
        data = self._request(name, canton)
        if data is None:
            # Error (non-200/timeout): do NOT cache (retry on next run)
            return None
        facts = _parse(data)
        if facts is not None:
            cache.put(ck, facts.__dict__)
        else:
            # Zero or ambiguous match: cache negative hit to avoid repeat calls
            cache.put(ck, {"_miss": True})
        return facts
```

### Pattern 2: _parse() — conservative match rule

```python
# Source: derived from API contract + AC5 "no wrong attribution" rule

def _parse(results: list) -> "ZefixFacts | None":
    """Exactly 1 result -> ZefixFacts; 0 or >1 -> None (ambiguous = nicht gefunden)."""
    if len(results) != 1:
        return None  # 0 = not found, >1 = ambiguous — never guess
    r = results[0]
    try:
        lf_short_de = r["legalForm"]["shortName"]["de"]   # "AG", "GmbH", "KlG", …
        lf_short_fr = r["legalForm"]["shortName"]["fr"]   # "SA", "Sàrl", …
        status = r["status"]                              # "ACTIVE"/"CANCELLED"/"BEING_CANCELLED"
        uid = r.get("uid") or ""
        legal_seat = r.get("legalSeat") or ""
        ehraid = r.get("ehraid")
        source_url = (
            f"https://www.zefix.admin.ch/de/search/entity/{ehraid}/info"
            if ehraid else ""
        )
        return ZefixFacts(
            legal_form_de=lf_short_de,
            legal_form_fr=lf_short_fr,
            status=status,
            uid=uid,
            legal_seat=legal_seat,
            source_url=source_url,
            source="zefix",
        )
    except (KeyError, TypeError):
        return None
```

### Pattern 3: Negative-hit caching

Negative hits (0 or >1 results) MUST be cached to avoid repeating expensive API calls on the same ambiguous name across runs. Use `{"_miss": True}` as the payload in the same `zefix-v1` namespace.

```python
# On cache.get(): distinguish hit vs miss vs negative-hit:
cached = cache.get(ck)
if cached is not None:
    if cached.get("_miss"):
        return None          # negative hit from prior run
    return ZefixFacts(**cached)
```

This means cache.get() returning a dict with `_miss=True` is a cache hit that means "we already know this name has no unambiguous Zefix record." Only non-200 / timeout errors are NOT cached (they should be retried next run).

### Pattern 4: _request() — POST with Basic Auth, Semaphore, Retry-After backoff

```python
# Source: mirrors pagespeed.py _request() exactly

ENDPOINT = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"
_RETRYABLE = (429, 500, 502, 503, 504)
_MAX_ATTEMPTS = 3

def _request(self, name: str, canton: str | None) -> "list | None":
    body = {"name": name, "activeOnly": False}
    if canton:
        body["canton"] = canton
    headers = {
        "Authorization": f"Basic {self._auth}",
        "Content-Type": "application/json",
    }
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with self._sem:
                r = requests.post(
                    f"{ENDPOINT}/company/search",
                    json=body,
                    headers=headers,
                    timeout=self._timeout,
                )
        except requests.RequestException:
            return None
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                return None
        if r.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
            self._sleep(_backoff_delay(getattr(r, "headers", {}), attempt))
            continue
        return None
    return None
```

**Reuse `_backoff_delay` and `_parse_retry_after` from pagespeed.py:** These are pure functions with no PSI-specific logic. Options:
1. **Duplicate minimally** into `zefix.py` (two copies, trivial functions) — simpler, no shared-module coupling.
2. **Extract to `lead_analyzer/clients/_backoff.py`** — cleaner but adds a file.

**Recommendation:** Duplicate minimally into `zefix.py` for now. The functions are 10 lines each and this phase has a clear scope. Mark as a future refactor candidate.

### Pattern 5: ZefixFacts dataclass (models.py)

```python
# Add to models.py alongside PaymentEstimate

@dataclass
class ZefixFacts:
    """Authoritative data from Zefix commercial register (AC5/NACH-01).

    All fields JSON-native so __dict__ round-trips through cache.put/get.
    source: "zefix" = authoritative lookup; "heuristik" = fallback (not set here,
    used downstream as signal label); "nicht-gefunden" = no unambiguous match.
    ZefixFacts is only constructed for the "zefix" case — None signals the other two.
    """
    legal_form_de: str        # "AG", "GmbH", "KlG", "Einzelunternehmen", etc.
    legal_form_fr: str        # "SA", "Sàrl", etc. (Romandie companies)
    status: str               # "ACTIVE" / "CANCELLED" / "BEING_CANCELLED"
    uid: str                  # "CHE-123.456.789" — cited as source in log
    legal_seat: str           # commune name (not canton abbrev — only in CompanyFull)
    source_url: str           # "https://www.zefix.admin.ch/de/search/entity/{ehraid}/info"
    source: str = "zefix"     # always "zefix" when this object exists
```

### Pattern 6: payment.estimate() — accepts optional zefix_facts

```python
# EDIT lead_analyzer/analyzers/payment.py

def estimate(record, fr, soup, config, zefix_facts=None) -> PaymentEstimate:
    """Augmented: if zefix_facts provided, Group A uses authoritative legal form."""
    name = str((record.cells.get("Kundenname") if record else None) or "")
    branche = str((record.cells.get("Branche") if record else None) or "")

    # Group A: Zefix authoritative > name heuristic
    if zefix_facts is not None:
        pa, na = _legal_form_from_zefix(zefix_facts)
    else:
        pa, na = _legal_form(name)          # existing offline heuristic (unchanged)

    pb, nb = _branch_tier(branche)
    pc, nc = _size_signals(soup)
    # ... rest unchanged
```

**`_legal_form_from_zefix(facts: ZefixFacts)` scoring map:**

| Zefix legalForm.shortName.de | Points | Signal note |
|---|---|---|
| "AG" | 2 | `Rechtsform AG (Zefix, autoritativ)` |
| "SA" | 2 | `Rechtsform SA (Zefix, autoritativ)` |
| "GmbH" | 1 | `Rechtsform GmbH (Zefix, autoritativ)` |
| "Sàrl", "Sarl" | 1 | `Rechtsform Sàrl (Zefix, autoritativ)` |
| "KlG" | 1 | `Rechtsform KlG (Zefix, autoritativ)` |
| "& Co" / "KmG" | 1 | `Rechtsform KmG/& Co (Zefix, autoritativ)` |
| "Einzelunternehmen" | 0 | `Rechtsform Einzelunternehmen (Zefix, autoritativ)` |
| any other | 0 | `Rechtsform unbekannt: {lf_de} (Zefix, autoritativ)` |

**Status modifier** (applied AFTER Group A+B+C aggregation, as a clamped penalty):

| Zefix status | Modifier | Signal note |
|---|---|---|
| `"ACTIVE"` | 0 (no change) | none |
| `"BEING_CANCELLED"` | -1 (clamp to 1) | `Status: in Liquidation (Zefix)` |
| `"CANCELLED"` | -2 (clamp to 1) | `Status: gelöscht (Zefix)` |

This makes a cancelled AG score lower than an active GmbH, which is correct per CLAUDE.md §3 (Zahlungskräftigkeit = lohnender? A deleted company is not a viable customer).

**Fallback signal labels** (for the JSONL run-log, NACH-01):
- ZefixFacts present: `"Quelle: Zefix (CHE-…)"` in signals
- ZefixFacts None + name-heuristic fired: `"Quelle: Namens-Heuristik"` (already labeled in existing code)
- ZefixFacts None + no name signal: `"Zefix: nicht gefunden (Name nicht eindeutig)"` added to notes

### Pattern 7: Config additions

```python
# EDIT lead_analyzer/config.py — add to Config dataclass:
use_zefix: bool = True          # gated via ZEFIX_USER/ZEFIX_PASSWORD presence
zefix_concurrency: int = 2      # Semaphore cap (conservative for public-sector API)
zefix_budget: int = 200         # max Zefix calls per run
```

`use_zefix=True` is the default because — just like `use_pagespeed=True` — the `from_config` gating already prevents any network call when credentials are absent. The flag is available for `--no-zefix` CLI override.

### Pattern 8: pipeline.run() — single-client build

```python
# EDIT pipeline.run() — mirrors the ps_client pattern exactly:
from .clients.zefix import ZefixClient

def run(config: Config) -> dict:
    # ... existing setup ...
    ps_client = PageSpeedClient.from_config(config)
    zx_client = ZefixClient.from_config(config)   # NEW: None without creds

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(analyze_row, r, url_col, config, ps_client, zx_client): i
            for i, r in enumerate(records)
        }
    # ... rest unchanged
```

```python
# EDIT analyze_row signature:
def analyze_row(
    record: RowRecord, url_col: str, config: Config,
    ps_client=None, zx_client=None         # both keyword, both default None
) -> RowResult:
    # ...
    # Zefix lookup before payment.estimate:
    zefix_facts = None
    if zx_client is not None and zx_client.is_available():
        raw_name = str(record.cells.get("Kundenname") or "")
        canton_hint = str(record.cells.get("Kanton") or "")   # optional column
        zefix_facts = zx_client.lookup(raw_name, canton_hint or None)
    est = payment.estimate(record, fr, soup, config, zefix_facts=zefix_facts)
```

**Canton hint:** If a "Kanton" column exists in the input table, pass it to `lookup()` as the `canton` parameter to disambiguate companies with the same name in different cantons. If the column is absent, pass `None` — the search still works.

**Name passed to Zefix:** Use the raw `Kundenname` cell value. Do NOT strip legal-form suffixes before the lookup — Zefix's own search handles partial matches (prefix search). Sending "Muster AG" will return Zefix records whose name begins with "Muster AG". Sending just "Muster" risks too many matches.

### Anti-Patterns to Avoid

- **Caching errors:** Non-200 / timeout responses must NOT be cached (transient failures should be retried next run). Only successful `_miss` (0 or >1 results) and successful hits are cached.
- **Guessing on ambiguous match:** If `len(results) > 1`, return `None` and fall back to the name heuristic. Never pick the first result of an ambiguous list (AC5).
- **Calling Zefix for empty/missing customer name:** Guard `if not raw_name.strip(): return None` before the lookup. An empty name search would likely explode the result count or return an error.
- **Calling Zefix inside the per-row Exception boundary:** The `zx_client.lookup()` call already never raises (by contract), so no extra try/except is needed around it. The outer `analyze_row` boundary catches any unexpected exception.
- **Re-raising from the ZefixClient:** `lookup()` must never raise. Match `pagespeed.py`'s pattern exactly: every exception path returns `None`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cache namespace isolation | New cache module | Existing `cache.key_for(["zefix-v1", name, canton])` | Already handles SHA-256 keying, atomic writes, schema_version |
| Thread safety for budget/semaphore | Custom locking | `_Budget` + `threading.Semaphore` from pagespeed.py | Pattern already proven; duplicate the two classes into zefix.py |
| Basic Auth encoding | Custom encoding | `base64.b64encode(f"{u}:{p}".encode()).decode()` | One line; no library needed |
| Retry-After parsing | Custom header parser | Copy `_backoff_delay` + `_parse_retry_after` from pagespeed.py | Identical logic; safe to duplicate |

---

## Common Pitfalls

### Pitfall 1: CompanyShort has no canton field
**What goes wrong:** Planner expects canton abbreviation (e.g., "ZH") in the search result. CompanyShort returns `legalSeat` (commune name, e.g., "Zürich") and `legalSeatId` but NOT the 2-char `canton` abbreviation.
**Why it happens:** The `canton` field only exists in `CompanyFull` (GET /company/uid/{id} response).
**How to avoid:** Use `legalSeat` (commune name) as the seat info in ZefixFacts. If the canton abbreviation is truly needed, a second GET call is required — out of scope for this phase.
**Warning signs:** Code that accesses `result["canton"]` on a search result will get `KeyError`.
[VERIFIED: OpenAPI CompanyShort schema — canton absent; CompanyFull schema — canton present]

### Pitfall 2: capitalNominal not in search response
**What goes wrong:** Expecting capital data from the search endpoint to enhance scoring.
**Why it happens:** `capitalNominal` and `capitalCurrency` are only in `CompanyFull`.
**How to avoid:** Capital/size stay as Group C HTML heuristic. Don't add a second GET call for this phase. Per AC5: "fehlt die Datenlage, konservativ schätzen und kennzeichnen."
[VERIFIED: OpenAPI CompanyShort vs CompanyFull schemas]

### Pitfall 3: Ambiguous match → wrong attribution
**What goes wrong:** Using `results[0]` when there are multiple matches for a common name (e.g., "Müller GmbH").
**Why it happens:** Tempting to "pick the best" match.
**How to avoid:** Hard rule: `len(results) != 1` → return None, fall back to name heuristic. Cache as negative hit so we don't retry.
**Warning signs:** Signals in run-log claiming "Zefix autoritativ" for a company that is actually a different entity.

### Pitfall 4: Caching errors (transient failures)
**What goes wrong:** A timeout gets cached as a negative hit; the company never gets looked up again even when the API is available.
**Why it happens:** Conflating "no result found" (permanent) with "network error" (transient).
**How to avoid:** Only cache successful API responses (hit and `{"_miss": True}` negative). Return `None` from `_request()` on errors WITHOUT caching.
**Warning signs:** After fixing a transient outage, companies still get heuristic scores.

### Pitfall 5: Name minLength 3 requirement
**What goes wrong:** Sending a 1- or 2-character name gets a 400 Bad Request from Zefix.
**Why it happens:** CompanySearchQuery has `minLength: 3` on the `name` field.
**How to avoid:** Guard: `if len(raw_name.strip()) < 3: return None` before calling `_request`.
[VERIFIED: OpenAPI CompanySearchQuery schema — name minLength: 3]

### Pitfall 6: Retry-After header not documented for Zefix
**What goes wrong:** Assuming Zefix sends Retry-After headers like PSI.
**Why it happens:** PSI explicitly documents 429 + Retry-After; Zefix documentation is silent.
**How to avoid:** Implement `_parse_retry_after` the same way as pagespeed.py — it checks the header but gracefully falls back to exponential backoff if the header is absent or unparseable. Conservative minimum: 1 s inter-request (per TenderLift client documentation).
[CITED: github.com/TenderLift/zefix-client README — "minIntervalMs: 1000"]
[ASSUMED: Zefix sends 429 on overload; no official documentation found — treat conservatively]

### Pitfall 7: activeOnly=false is the right default
**What goes wrong:** Using `activeOnly=true` causes cancelled companies (Bedarf high, Kaufkraft low) to return zero results, falling back to the name heuristic and potentially scoring them too high.
**Why it happens:** activeOnly=true is the natural first choice.
**How to avoid:** Use `activeOnly=false` so CANCELLED and BEING_CANCELLED companies are found and their status can apply the score penalty.

### Pitfall 8: UID format from search vs detail URL
**What goes wrong:** The `uid` field in CompanyShort is formatted as "CHE-123.456.789" (with dashes and dots). The GET /company/uid/{id} endpoint expects "CHE102909703" (no dashes/dots, per Bruno collection example).
**Why it happens:** Two different UID representations exist in the Zefix system.
**How to avoid:** For the source_url, use `ehraid` which is always a clean integer: `https://www.zefix.admin.ch/de/search/entity/{ehraid}/info`. This is always safe.
[VERIFIED: Bruno collection — `GET .../company/uid/CHE102909703`]

---

## Score Composition (Exact Logic)

### Group A replacement with Zefix data

Existing `_legal_form(name)` in `payment.py` is NOT replaced — it's kept as the fallback for `zefix_facts=None`. A new `_legal_form_from_zefix(facts)` function is added alongside it.

```python
def _legal_form_from_zefix(facts: "ZefixFacts") -> tuple[int, list[str]]:
    """Group A from authoritative Zefix data. Maps legalForm.shortName.de to points."""
    lf = facts.legal_form_de  # "AG", "GmbH", "Einzelunternehmen", …
    # Use same scoring as the existing _LEGAL table:
    if lf in ("AG", "SA"):
        pts, label = 2, lf
    elif lf in ("GmbH", "Sàrl", "Sarl", "KlG") or "&" in lf:
        pts, label = 1, lf
    elif lf == "Einzelunternehmen":
        pts, label = 0, lf
    else:
        pts, label = 0, lf   # unknown legal form → conservative 0 (no invented facts)
    note = f"Rechtsform {label} aus Zefix (autoritativ, Quelle: {facts.uid})"
    return pts, [note]
```

### Status modifier (applied after _map_to_1_5)

```python
def _status_modifier(facts: "ZefixFacts | None") -> tuple[int, list[str]]:
    if facts is None:
        return 0, []
    if facts.status == "ACTIVE":
        return 0, []
    if facts.status == "BEING_CANCELLED":
        return -1, [f"Status: in Liquidation (Zefix, {facts.source_url})"]
    if facts.status == "CANCELLED":
        return -2, [f"Status: gelöscht (Zefix, {facts.source_url})"]
    return 0, []

# In estimate():
raw_score = _map_to_1_5(pa + pb + pc)
penalty, penalty_notes = _status_modifier(zefix_facts)
zahl = scoring.clamp_score(raw_score + penalty)
notes += penalty_notes
```

### Byte-identical offline fallback

When `zefix_facts is None` (no creds, lookup failed, ambiguous, empty name), `estimate()` calls the existing `_legal_form(name)` path. The `resolved` predicate logic is unchanged. The output is byte-identical to Phase 7 for every row where Zefix is OFF or returns no result.

---

## Wiring (File-Level Anchors)

| File | Change | Anchor |
|---|---|---|
| `lead_analyzer/clients/zefix.py` | NEW FILE | — |
| `lead_analyzer/models.py` | Add `ZefixFacts` dataclass | After `PaymentEstimate` (line ~42) |
| `lead_analyzer/config.py` | Add `use_zefix: bool = True`, `zefix_concurrency: int = 2`, `zefix_budget: int = 200` | After `pagespeed_budget` (~line 66) |
| `lead_analyzer/analyzers/payment.py` | Add `zefix_facts=None` param to `estimate()`; add `_legal_form_from_zefix()`; add `_status_modifier()` | `estimate()` signature at line 141; new functions after `_legal_form()` |
| `lead_analyzer/pipeline.py` | Add `ZefixClient` import; build `zx_client = ZefixClient.from_config(config)` in `run()`; pass `zx_client` to `analyze_row`; add Zefix lookup in `analyze_row` | `run()` at line 111; `analyze_row` signature at line 28; inside `analyze_row` before `payment.estimate` call at line 80 |
| `tests/test_zefix_client.py` | NEW FILE | — |
| `tests/test_payment.py` | Add tests for `estimate()` with `zefix_facts=` scenarios | Existing file |

---

## Runtime State Inventory

This is not a rename/refactor/migration phase. No runtime state changes required.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `requests` | ZefixClient HTTP POST | Yes | Already installed | — |
| `ZEFIX_USER` env var | ZefixClient.from_config() | Unknown (user must obtain) | — | None → offline heuristic (AC9) |
| `ZEFIX_PASSWORD` env var | ZefixClient.from_config() | Unknown (user must obtain) | — | None → offline heuristic (AC9) |
| Zefix PROD API | lookup() | Assumed accessible with creds | v2.7.2.3 | Offline heuristic |

**Missing dependencies with fallback:**
- `ZEFIX_USER`/`ZEFIX_PASSWORD`: User must request credentials from zefix@bj.admin.ch. Without them, `from_config()` returns `None` and the run is byte-identical to Phase 7. This is the designed zero-setup path (AC9).

**Missing dependencies with no fallback:** None — the entire Zefix integration is optional by design.

---

## Validation Architecture

nyquist_validation is enabled (config.json: key absent = treat as true).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `pytest tests/test_zefix_client.py tests/test_payment.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIFF-01 | from_config returns None without creds → offline-identical | unit | `pytest tests/test_zefix_client.py::test_unavailable_without_creds -x` | ❌ Wave 0 |
| DIFF-01 | POST search 200 + exactly 1 result → ZefixFacts parsed | unit | `pytest tests/test_zefix_client.py::test_single_match_parsed -x` | ❌ Wave 0 |
| DIFF-01 | 0 results → None (negative cached) | unit | `pytest tests/test_zefix_client.py::test_zero_results_none -x` | ❌ Wave 0 |
| DIFF-01 | >1 results → None (ambiguous, negative cached) | unit | `pytest tests/test_zefix_client.py::test_ambiguous_none -x` | ❌ Wave 0 |
| DIFF-01 | Timeout → None, no raise | unit | `pytest tests/test_zefix_client.py::test_timeout_none -x` | ❌ Wave 0 |
| DIFF-01 | 429 → retry with sleep, then None | unit | `pytest tests/test_zefix_client.py::test_429_retry_capped -x` | ❌ Wave 0 |
| DIFF-01 | Budget=0 → None without network call | unit | `pytest tests/test_zefix_client.py::test_budget_exhausted -x` | ❌ Wave 0 |
| DIFF-01 | Cache hit → return without network and without budget | unit | `pytest tests/test_zefix_client.py::test_cache_hit_no_network -x` | ❌ Wave 0 |
| DIFF-01 | Negative cache hit (_miss) → None without network | unit | `pytest tests/test_zefix_client.py::test_negative_cache_hit -x` | ❌ Wave 0 |
| DIFF-01 | Short name (<3 chars) → None without network call | unit | `pytest tests/test_zefix_client.py::test_short_name_guard -x` | ❌ Wave 0 |
| ZK-01/NACH-01 | estimate with zefix_facts AG ACTIVE → zahl boosted, signal logged | unit | `pytest tests/test_payment.py::test_zefix_ag_active -x` | ❌ Wave 0 |
| ZK-01/NACH-01 | estimate with zefix_facts GmbH CANCELLED → penalty applied, signal logged | unit | `pytest tests/test_payment.py::test_zefix_gmbh_cancelled -x` | ❌ Wave 0 |
| DIFF-01 | estimate zefix_facts=None → byte-identical to existing offline baseline | unit | `pytest tests/test_payment.py::test_zefix_none_fallback -x` | ❌ Wave 0 |
| PERF-02 | Full run without creds → no ZefixClient created, no network | integration | `pytest tests/test_pipeline_dim1.py -x` (existing, must still pass) | ✅ |

### Sampling Rate
- **Per task commit:** `pytest tests/test_zefix_client.py tests/test_payment.py -x -q`
- **Per wave merge:** `pytest -x -q` (full suite, currently 206 tests)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_zefix_client.py` — all ZefixClient unit tests (mirrors test_pagespeed_client.py)
- [ ] Additional test functions in `tests/test_payment.py` — zefix_facts scenarios

---

## Security Domain

ASVS enforcement enabled (config key absent = enabled).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes (API credentials) | HTTP Basic Auth via env vars; never hardcoded; `.env` not committed (SETUP-03) |
| V3 Session Management | No | CLI tool, no sessions |
| V4 Access Control | No | No user-facing access control |
| V5 Input Validation | Yes | `name.strip()`, minLength guard (≥3 chars), `canton` passed through only if non-empty |
| V6 Cryptography | No | Credentials transmitted over HTTPS (Zefix enforces TLS — verified via curl above) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Credential leakage in logs | Info Disclosure | Never log `ZEFIX_USER`/`ZEFIX_PASSWORD`; only log `uid` (public) in signals |
| Path traversal via cache key | Tampering | `cache.key_for()` uses SHA-256 hex digest — already verified safe (T-05-02) |
| Name injection in POST body | Tampering | `requests.post(json=body)` auto-encodes JSON; no string interpolation into request body |
| Invented facts from ambiguous match | Repudiation | Hard rule: >1 result → None → heuristic. Logged as "nicht gefunden". |

---

## Code Examples

### Exact request shape (verified from validitylabs/zefix source)

```python
# Source: github.com/validitylabs/zefix/blob/main/src/search.ts
# Verified POST body from TypeScript source:
import requests, base64

auth = base64.b64encode(b"user@example.com:password123").decode()
resp = requests.post(
    "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search",
    json={"name": "Muster AG", "activeOnly": False},
    headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
    },
    timeout=(5.0, 15.0),
)
results = resp.json()  # list of CompanyShort dicts
```

### Exact parse paths (verified from jschwendener/zefix-php Company.fromData)

```python
# Source: github.com/jschwendener/zefix-php/blob/main/src/DTO/Company.php
# All field names confirmed from the official OpenAPI spec:
r = results[0]
legal_form_de  = r["legalForm"]["shortName"]["de"]   # "AG"
legal_form_fr  = r["legalForm"]["shortName"]["fr"]   # "SA"
legal_form_id  = r["legalForm"]["id"]                # int (e.g., 3 for AG)
status         = r["status"]                         # "ACTIVE"
uid            = r["uid"]                            # "CHE-123.456.789"
legal_seat     = r["legalSeat"]                      # "Zürich"
ehraid         = r["ehraid"]                         # int
source_url     = f"https://www.zefix.admin.ch/de/search/entity/{ehraid}/info"
```

### test_zefix_client.py scaffold (mirrors test_pagespeed_client.py)

```python
# Source: mirrors tests/test_pagespeed_client.py structure exactly

_VALID_BODY = [
    {
        "name": "Muster AG",
        "ehraid": 12345678,
        "uid": "CHE-123.456.789",
        "legalSeat": "Zürich",
        "legalSeatId": 261,
        "registryOfCommerceId": 20,
        "legalForm": {
            "id": 3,
            "uid": "0106",
            "name": {"de": "Aktiengesellschaft", "fr": "Société anonyme", "it": "SA", "en": "Corp"},
            "shortName": {"de": "AG", "fr": "SA", "it": "SA", "en": "Ltd"},
        },
        "status": "ACTIVE",
        "sogcDate": "2023-04-15",
        "deletionDate": None,
    }
]

def _client(sleep=lambda *_: None, budget=200):
    from lead_analyzer.clients import zefix as zx_mod
    import threading
    sem = threading.Semaphore(2)
    budget_obj = zx_mod._Budget(budget)
    return ZefixClient("u", "p", sem, budget_obj, (5.0, 15.0), sleep=sleep)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Name-string heuristic for legal form (Group A) | Authoritative Zefix lookup (optional, gated) | Phase 8 | Removes false positives like "Magazin GmbH" misidentified as GmbH; now verified |
| No status signal | Zefix `status` field (ACTIVE/CANCELLED/BEING_CANCELLED) | Phase 8 | Cancelled companies get score penalty — correct per CLAUDE.md §3 |

**Not changed in this phase:**
- Group B (branch tier)
- Group C (HTML size signals)
- capitalNominal / employee count — remain "unknown" (would require second GET call; out of scope per AC5)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Zefix API sends 429 when rate-limited (not 503 or connection drop) | Rate limits / Common Pitfalls | Backoff logic still works — `_RETRYABLE` includes 429, 500, 502, 503, 504 |
| A2 | Zefix source_url pattern `https://www.zefix.admin.ch/de/search/entity/{ehraid}/info` resolves to a valid company page | Code Examples | Source URL in signals may be a dead link; audit trail value but not functional |
| A3 | `legalForm.shortName.de` for Einzelfirma is "Einzelunternehmen" (not "Einzelfirma") | Score Composition | If wrong, the legal form would fall into the "unknown → 0" bucket — conservative, not catastrophic; easily fixed by checking live API |
| A4 | Zefix does not publish explicit rate limits; 1 s minimum inter-request is a safe/conservative default | Rate limits | If API has stricter limits, `zefix_concurrency=2` + `zefix_budget=200` may still trigger throttling; mitigated by Retry-After backoff |

A1 and A4 are operational but non-catastrophic. A3 should be verified with a live test call once credentials are available.

---

## Open Questions

1. **Exact `legalForm.shortName.de` for Einzelfirma**
   - What we know: PHP enum has "Einzelunternehmen" in full name; shortName.de may differ
   - What's unclear: Whether shortName.de is "Einzelfirma", "EU", "Einzelunternehmen", or something else
   - Recommendation: Wave 0 test fixture uses "Einzelunternehmen"; after credential acquisition, do one live lookup of a known Einzelfirma and confirm. The score outcome (0 pts) is the same regardless of the exact string, so this is low risk.

2. **Maximum result count from POST /company/search**
   - What we know: Error type `RESULTLIST_TO_LARGE` exists in the spec
   - What's unclear: What the actual limit is (100? 500?) and whether it returns HTTP 400 or a partial 200
   - Recommendation: Treat any 400 as a non-200 → None → fallback. The guard `len(results) > 1 → None` already handles large ambiguous result sets conservatively.

3. **TEST vs PROD for pre-credential testing**
   - What we know: TEST base is `https://www.zefixintg.admin.ch/ZefixPublicREST/api/v1`
   - What's unclear: Whether the test environment is accessible with the same credentials as production
   - Recommendation: Add `ZEFIX_BASE_URL` as an optional config env var (default PROD URL) so the planner can wire it. Integration tests should use the TEST URL if credentials are available.

---

## Sources

### Primary (HIGH confidence)
- [TenderLift/zefix-client spec/zefix.json](https://github.com/TenderLift/zefix-client/blob/main/spec/zefix.json) — official OpenAPI spec v2.7.2.3, all schemas verified (CompanyShort, CompanyFull, CompanySearchQuery, ErrorDetails)
- [validitylabs/zefix src/search.ts](https://github.com/validitylabs/zefix/blob/main/src/search.ts) — verified POST request shape, Basic Auth header, response interface
- [validitylabs/zefix src/details.ts](https://github.com/validitylabs/zefix/blob/main/src/details.ts) — verified IDetailsResult fields (CompanyFull mapping)
- [jschwendener/zefix-php src/DTO/Company.php](https://github.com/jschwendener/zefix-php/blob/main/src/DTO/Company.php) — verified all response field names from fromData()
- [jschwendener/zefix-php src/Enums/CompanyStatus.php](https://github.com/jschwendener/zefix-php/blob/main/src/Enums/CompanyStatus.php) — status enum: ACTIVE, CANCELLED, BEING_CANCELLED
- [jschwendener/zefix-php .bruno/Zefix/Search Company.bru](https://github.com/jschwendener/zefix-php/blob/main/.bruno/Zefix/Search%20Company.bru) — verified PROD endpoint URL and Basic Auth
- [lead_analyzer/clients/pagespeed.py](../../../lead_analyzer/clients/pagespeed.py) — pattern to mirror exactly
- [lead_analyzer/cache.py](../../../lead_analyzer/cache.py) — cache API (`key_for`, `get`, `put`, `set_cache_dir`)
- [lead_analyzer/analyzers/payment.py](../../../lead_analyzer/analyzers/payment.py) — existing Group A/B/C logic to augment
- [lead_analyzer/models.py](../../../lead_analyzer/models.py) — dataclass conventions
- [lead_analyzer/pipeline.py](../../../lead_analyzer/pipeline.py) — single-client build pattern
- [lead_analyzer/config.py](../../../lead_analyzer/config.py) — Config dataclass + load_dotenv pattern

### Secondary (MEDIUM confidence)
- [TenderLift/zefix-client README](https://github.com/TenderLift/zefix-client) — rate limit indication: "minIntervalMs: 1000" (1 s minimum between requests)
- [jschwendener/zefix-php README](https://github.com/jschwendener/zefix-php/blob/main/readme.md) — auth request via zefix@bj.admin.ch

### Tertiary (LOW confidence, flagged in Assumptions Log)
- Zefix rate-limit behavior (429 vs other codes) — no official documentation found; A1 and A4 in Assumptions Log

---

## Metadata

**Confidence breakdown:**
- API contract (endpoints, schemas, field names): HIGH — verified from official OpenAPI spec + 3 independent client implementations
- Architecture / wiring: HIGH — verified against existing codebase (pagespeed.py, payment.py, pipeline.py, config.py)
- Rate limits / fair use: LOW-MEDIUM — no official docs; mitigated by conservative defaults
- Score composition: HIGH — derived directly from existing payment.py logic + verified status enum

**Research date:** 2026-06-15
**Valid until:** 2026-09-15 (stable public-sector API; low churn expected)

---

## RESEARCH COMPLETE
