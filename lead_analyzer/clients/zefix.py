"""Optionaler, ratenlimitierter Zefix-Client (PERF-02, AC5/AC7/AC8).

Dies ist die EINZIGE Komponente, die das Zefix-Handelsregister beruehrt. Sie ist
hart abgesichert und spiegelt clients/pagespeed.py nahezu identisch:

- **Gated**: ohne `ZEFIX_USER` UND `ZEFIX_PASSWORD` gibt es keinen Client
  (`from_config` -> None); Standard ist also OFF, der Offline-Lauf bleibt byte-identisch.
- **Gekappte Nebenlaeufigkeit**: eine `threading.Semaphore(zefix_concurrency)` laesst nie
  mehr als N Zefix-Calls gleichzeitig in-flight.
- **Per-Lauf-Budget**: ein thread-sicherer Zaehler (`_Budget`) kappt die Gesamtzahl der
  Calls pro Lauf (`zefix_budget`) — ein 429-Sturm kann den Lauf nicht in die Laenge
  ziehen (PERF-02).
- **Backoff mit Jitter, Retry-After-bewusst**: bei 429/5xx wird gekappt (3 Versuche)
  zurueckgestaffelt; der `sleep` ist INJIZIERT (Default `time.sleep`, Tests uebergeben ein
  No-Op -> KEINE echten Wartezeiten).
- **Eigener Cache-Namespace**: jedes Resultat wird unter `cache.key_for(["zefix-v1",
  name, canton])` gecacht; ein Cache-Hit kostet WEDER Netz NOCH Budget. Fehler werden
  NICHT gecacht (nur erfolgreiche Resultate und Negativ-Treffer / {"_miss": True}).
- **None bei JEDEM Fehler, NIE ein Raise**: Timeout/non-200/malformed-JSON/429-nach-
  Retries/Budget-erschoepft -> `lookup()` liefert `None`. So kann ein Zefix-Problem nie
  den Per-Zeilen-Pfad crashen (AC4/AC8).
- **Sicherheit**: Credentials leben nur in `self._auth` (base64); werden NIE geloggt,
  gecacht oder andersweitig serialisiert (T-08-01).

[CITED: 08-RESEARCH.md Patterns 1-5; Pitfalls 1/3/4/5/7/8; threat model T-08-01/02]
"""

from __future__ import annotations

import base64
import os
import random
import threading
import time

import requests

from .. import cache
from ..models import ZefixFacts

# Zefix Public REST API v1 — PROD endpoint.
# [CITED: 08-RESEARCH.md §"Zefix API Contract" + jschwendener/zefix-php .bruno auth:basic]
ENDPOINT = "https://www.zefix.admin.ch/ZefixPublicREST/api/v1"

# Retry-faehige HTTP-Status (Quota/Server). Alles andere -> sofort None.
_RETRYABLE = (429, 500, 502, 503, 504)
# Gekappte Versuche: max. 3 requests.post pro lookup() (1 + 2 Retries).
_MAX_ATTEMPTS = 3
# Zefix CompanySearchQuery: name hat minLength: 3.
# [VERIFIED: 08-RESEARCH.md Pitfall 5 + OpenAPI CompanySearchQuery schema]
_MIN_NAME_LEN = 3


class _Budget:
    """Thread-sicherer Per-Lauf-Zaehler, der die Gesamtzahl der Zefix-Calls kappt (PERF-02).

    `try_consume()` dekrementiert und liefert True, solange noch Budget uebrig ist; sonst
    False (kein Call). `exhausted()` ist True, sobald nichts mehr uebrig ist. Ein `Lock`
    serialisiert die Read-Modify-Write-Sequenz ueber alle Worker-Threads (AC8).

    [COPIED VERBATIM from clients/pagespeed.py — future refactor candidate]
    """

    def __init__(self, n: int) -> None:
        self._remaining = int(n)
        self._lock = threading.Lock()

    def try_consume(self) -> bool:
        """Verbraucht eine Einheit, falls vorhanden -> True; sonst False (kein Netz)."""
        with self._lock:
            if self._remaining <= 0:
                return False
            self._remaining -= 1
            return True

    def exhausted(self) -> bool:
        """True gdw. kein Budget mehr uebrig ist."""
        with self._lock:
            return self._remaining <= 0


class ZefixClient:
    """Optionaler Zefix-Client: `is_available()`, `lookup(name) -> ZefixFacts | None`.

    Pro Lauf wird GENAU EINE Instanz gebaut (`from_config`) — mit EINER geteilten
    Semaphore und EINEM geteilten Budget, das alle Worker-Threads gemeinsam nutzen.
    """

    def __init__(self, user, password, semaphore, budget, timeout, sleep=time.sleep) -> None:
        # Credentials als base64 codieren und NUR als self._auth speichern.
        # Rohe user/password werden NIEMALS als Attribute oder in Logs aufbewahrt (T-08-01).
        self._auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._sem = semaphore
        self._budget = budget
        self._timeout = timeout
        self._sleep = sleep  # injiziert -> Tests uebergeben ein No-Op, kein echtes Warten

    @classmethod
    def from_config(cls, config) -> "ZefixClient | None":
        """Baut den geteilten Client oder None (ohne Credentials kein Client).

        None gdw. `use_zefix` falsy ODER kein `ZEFIX_USER`/`ZEFIX_PASSWORD` in der
        Umgebung. Ohne Credentials bleibt der Lauf byte-identisch zur Phase-7-Baseline.
        [CITED: 08-RESEARCH.md Pattern 7 — gating mirrors pagespeed.py exactly]
        """
        if not getattr(config, "use_zefix", False):
            return None
        user = os.environ.get("ZEFIX_USER")
        password = os.environ.get("ZEFIX_PASSWORD")
        if not user or not password:
            return None
        return cls(
            user,
            password,
            threading.Semaphore(getattr(config, "zefix_concurrency", 2)),
            _Budget(getattr(config, "zefix_budget", 200)),
            # Zefix kann langsam antworten -> read-Timeout auf >= 15s anheben.
            (config.timeout_connect, max(config.timeout_read, 15.0)),
        )

    def is_available(self) -> bool:
        """True gdw. Credentials vorhanden sind UND das Budget noch nicht erschoepft ist."""
        return self._auth is not None and not self._budget.exhausted()

    def lookup(self, name: str, canton: str | None = None) -> "ZefixFacts | None":
        """Liefert ein ZefixFacts (200, genau 1 Treffer) oder None. Wirft NIE.

        Reihenfolge: Kurzname-Guard -> Cache-Hit -> Budget-Gate -> Netz -> Parse ->
        Cache (Treffer UND Negativ-Treffer). Transiente Fehler (Timeout/non-200) werden
        NICHT gecacht (Pitfall 4 — bei naechstem Lauf erneut versuchen).

        Cache-Key: ["zefix-v1", name, canton or ""] — Kanton in Key, um Verwechslungen
        zwischen gleicnnamigen Firmen in verschiedenen Kantonen zu verhindern.
        """
        # a) Kurzname-Guard: Zefix verlangt minLength 3 auf dem name-Feld (Pitfall 5).
        name = (name or "").strip()
        if len(name) < _MIN_NAME_LEN:
            return None  # kein Netz, kein Cache — sofort None

        # b) Cache-Hit kostet weder Netz noch Budget (AC7/AC8).
        ck = cache.key_for(["zefix-v1", name, canton or ""])
        cached = cache.get(ck)
        if cached is not None:
            # Negativ-Treffer: {"_miss": True} wurde gespeichert -> None (Pitfall 3).
            if cached.get("_miss"):
                return None
            return ZefixFacts(**cached)

        # c) Budget-Gate: erschoepft -> None OHNE Netz-Call.
        if not self._budget.try_consume():
            return None

        # d) Netz (gekappt, mit Backoff) — liefert list | None, wirft nie.
        data = self._request(name, canton)
        if data is None:
            # Transienter Fehler (Timeout/non-200): NICHT cachen (Pitfall 4).
            return None

        # e) Defensiv parsen — 0 oder >1 Treffer -> Negativ-Cache; genau 1 -> Treffer.
        facts = _parse(data)
        if facts is not None:
            cache.put(ck, facts.__dict__)  # Treffer cachen
        else:
            cache.put(ck, {"_miss": True})  # Negativ-Treffer cachen (Pitfall 3)
        return facts

    # --- Netz: gekappte Retries unter Semaphore, Retry-After-bewusst ---------- #

    def _request(self, name: str, canton: str | None) -> "list | None":
        """POST Zefix /company/search mit gekappten Retries + Backoff. Liefert list | None, wirft NIE.

        Die Semaphore umschliesst NUR das `requests.post` -> nie mehr als N in-flight (AC8).
        Bei 429/5xx wird (gekappt) zurueckgestaffelt; der `sleep` ist injiziert (Tests: No-Op).
        [CITED: 08-RESEARCH.md Pattern 4; Pitfall 7 activeOnly=false]
        """
        body: dict = {"name": name, "activeOnly": False}
        if canton:
            body["canton"] = canton
        headers = {
            "Authorization": f"Basic {self._auth}",
            "Content-Type": "application/json",
        }
        for attempt in range(_MAX_ATTEMPTS):
            try:
                with self._sem:  # Semaphore kappt die gleichzeitige In-flight-Zahl
                    r = requests.post(
                        f"{ENDPOINT}/company/search",
                        json=body,
                        headers=headers,
                        timeout=self._timeout,
                    )
            except requests.RequestException:
                # Timeout/Connection/etc. -> kein Raise, sondern Degradation (AC4).
                return None

            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError:
                    # Malformed JSON trotz 200 -> behandeln wie "Zefix fehlgeschlagen".
                    return None

            # Retry-faehig UND noch ein Versuch uebrig -> Backoff, dann erneut.
            if r.status_code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                self._sleep(_backoff_delay(getattr(r, "headers", {}), attempt))
                continue

            # Jeder andere Status / erschoepfte Retries -> None.
            return None
        return None


def _parse(results) -> "ZefixFacts | None":
    """Genau 1 Ergebnis -> ZefixFacts; 0 oder >1 -> None (ambiguous = nicht gefunden).

    Hard rule: nie den ersten Eintrag aus einer mehrdeutigen Liste verwenden (AC5/T-08-06).
    Alle Feld-Zugriffe sind in try/except gewrapped -> KeyError/TypeError -> None.

    source_url wird aus dem Integer `ehraid` konstruiert, NICHT aus einem URL-Feld in
    der Response (Sicherheit: T-08-02 — kein Echo von Fremd-URLs).
    [CITED: 08-RESEARCH.md Pattern 2 + Pitfall 3 + Code Examples]
    """
    if not isinstance(results, list) or len(results) != 1:
        return None  # 0 = nicht gefunden, >1 = ambiguous — nie raten (AC5)
    r = results[0]
    try:
        lf_short_de = r["legalForm"]["shortName"]["de"]   # "AG", "GmbH", "KlG", …
        lf_short_fr = r["legalForm"]["shortName"]["fr"]   # "SA", "Sarl", …
        status = r["status"]                              # "ACTIVE"/"CANCELLED"/"BEING_CANCELLED"
        uid = r.get("uid") or ""
        legal_seat = r.get("legalSeat") or ""
        ehraid = r.get("ehraid")
        # source_url aus ehraid (Integer) konstruieren — nie URL-Felder aus Response echo-en (T-08-02).
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


def _backoff_delay(headers, attempt: int) -> float:
    """Backoff-Dauer in Sekunden: Retry-After (falls parsebar) ODER exponentiell, je + Jitter.

    Retry-After hat Vorrang (Server-Wunsch honorieren, AC8); sonst 2**attempt. Der Jitter
    (`random.uniform`) entzerrt gleichzeitige Retries (Thundering-Herd-Vermeidung).

    [COPIED VERBATIM from clients/pagespeed.py — future refactor candidate]
    """
    retry_after = _parse_retry_after(headers.get("Retry-After") if headers else None)
    base = retry_after if retry_after is not None else float(2 ** attempt)
    return base + random.uniform(0.0, 0.5)


def _parse_retry_after(header) -> "float | None":
    """`Retry-After`-Header als Sekunden (int) lesen; nicht parsebar -> None.

    Zefix sendet moeglicherweise die Sekunden-Variante (nicht dokumentiert); das
    HTTP-Date-Format wird hier bewusst nicht unterstuetzt (dann greift der exponentielle
    Fallback). [CITED: 08-RESEARCH.md Pitfall 6]

    [COPIED VERBATIM from clients/pagespeed.py — future refactor candidate]
    """
    if header is None:
        return None
    try:
        return float(int(str(header).strip()))
    except (ValueError, TypeError):
        return None
