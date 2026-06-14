"""Optionaler, ratenlimitierter PageSpeed-Insights-Client (PERF-02, AC7/AC8).

Dies ist die EINZIGE Komponente, die das Netz berührt. Sie ist hart abgesichert:

- **Gated**: ohne `PAGESPEED_API_KEY` (und ohne `use_pagespeed`) gibt es keinen Client
  (`from_config` -> None); Standard ist also OFF, der Offline-Lauf bleibt byte-identisch.
- **Gekappte Nebenläufigkeit**: eine `threading.Semaphore(pagespeed_concurrency)` lässt nie
  mehr als N PSI-Calls gleichzeitig in-flight (< Worker-Zahl, sonst trippt das Quota).
- **Per-Lauf-Budget**: ein thread-sicherer Zähler (`_Budget`) kappt die Gesamtzahl der Calls
  pro Lauf (`pagespeed_budget`) — ein 429-Sturm kann den Lauf nicht in die Länge ziehen.
- **Backoff mit Jitter, Retry-After-bewusst**: bei 429/5xx wird gekappt (3 Versuche) zurück-
  gestaffelt; der `sleep` ist INJIZIERT (Default `time.sleep`, Tests übergeben ein No-Op ->
  KEINE echten Wartezeiten).
- **Eigener Cache-Namespace**: jedes Resultat wird unter `cache.key_for(["pagespeed-v1",
  "mobile", url])` gecacht; ein Cache-Hit kostet WEDER Netz NOCH Budget. Fehler werden NICHT
  gecacht.
- **None bei JEDEM Fehler, NIE ein Raise**: Timeout/non-200/malformed-JSON/429-nach-Retries/
  Budget-erschöpft -> `score()` liefert `None`. So kann ein PSI-Problem nie den Per-Zeilen-
  Pfad crashen oder einen Score verfälschen (Degradation -> Viewport-Heuristik).

[CITED: 06-RESEARCH.md "Client availability + score skeleton" + Pattern 4; Pitfalls 1/3/8]
"""

from __future__ import annotations

import os
import random
import threading
import time

import requests

from .. import cache
from ..models import PsResult

# PSI v5 runPagespeed. [CITED: 06-RESEARCH.md Pattern 4 / developers.google.com PSI v5]
ENDPOINT = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"

# Retry-fähige HTTP-Status (Quota/Server). Alles andere -> sofort None.
_RETRYABLE = (429, 500, 502, 503, 504)
# Gekappte Versuche: max. 3 requests.get pro score() (1 + 2 Retries).
_MAX_ATTEMPTS = 3


class _Budget:
    """Thread-sicherer Per-Lauf-Zähler, der die Gesamtzahl der PSI-Calls kappt (PERF-02).

    `try_consume()` dekrementiert und liefert True, solange noch Budget übrig ist; sonst
    False (kein Call). `exhausted()` ist True, sobald nichts mehr übrig ist. Ein `Lock`
    serialisiert die Read-Modify-Write-Sequenz über alle Worker-Threads (AC8).
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
        """True gdw. kein Budget mehr übrig ist."""
        with self._lock:
            return self._remaining <= 0


class PageSpeedClient:
    """Optionaler PSI-Client: `is_available()`, `score(url) -> PsResult | None`.

    Pro Lauf wird GENAU EINE Instanz gebaut (`from_config`) — mit EINER geteilten Semaphore
    und EINEM geteilten Budget, das alle Worker-Threads gemeinsam nutzen.
    """

    def __init__(self, key, semaphore, budget, timeout, sleep=time.sleep) -> None:
        self._key = key
        self._sem = semaphore
        self._budget = budget
        self._timeout = timeout
        self._sleep = sleep  # injiziert -> Tests übergeben ein No-Op, kein echtes Warten

    @classmethod
    def from_config(cls, config) -> "PageSpeedClient | None":
        """Baut den geteilten Client oder None (Standard OFF ohne Key).

        None gdw. `use_pagespeed` falsy ODER kein `PAGESPEED_API_KEY` in der Umgebung.
        [CITED: 06-RESEARCH.md A2 — default OFF unless PAGESPEED_API_KEY present]
        """
        if not getattr(config, "use_pagespeed", False):
            return None
        key = os.environ.get("PAGESPEED_API_KEY")
        if not key:  # ohne Key -> kein Client (AC9: zero-setup Offline-Lauf bleibt unverändert)
            return None
        return cls(
            key,
            threading.Semaphore(getattr(config, "pagespeed_concurrency", 2)),
            _Budget(getattr(config, "pagespeed_budget", 400)),
            # PSI-Lighthouse-Läufe sind langsam -> read-Timeout auf >= 30s anheben (A4).
            (config.timeout_connect, max(config.timeout_read, 30.0)),
        )

    def is_available(self) -> bool:
        """True gdw. ein Key vorhanden ist UND das Budget noch nicht erschöpft ist."""
        return self._key is not None and not self._budget.exhausted()

    def score(self, url: str):
        """Liefert ein geparstes `PsResult` (200) oder `None` bei JEDEM Fehler. Wirft NIE.

        Reihenfolge: Cache-Hit (kein Netz/Budget) -> Budget-Gate -> Netz -> Parse -> Cache.
        Fehler werden NICHT gecacht (nur erfolgreiche Resultate).
        """
        # 1) Cache-Hit kostet weder Netz noch Budget (Pitfall 3, AC7/AC8).
        ck = cache.key_for(["pagespeed-v1", "mobile", url])
        cached = cache.get(ck)
        if cached is not None:
            return PsResult(**cached)
        # 2) Budget-Gate: erschöpft -> None OHNE Netz-Call (Degradation -> Viewport).
        if not self._budget.try_consume():
            return None
        # 3) Netz (gekappt, mit Backoff) — liefert dict | None, wirft nie.
        data = self._request(url)
        if data is None:
            return None
        # 4) Defensiv parsen — malformed -> None (kein Score-Verfälschen).
        res = _parse(data)
        if res is not None:
            cache.put(ck, res.__dict__)  # nur ERFOLG cachen
        return res

    # --- Netz + Parse: in Task 2 gefüllt ----------------------------------- #

    def _request(self, url):  # pragma: no cover - Stub bis Task 2
        """Stub (Task 1): liefert None. Die echte Netz-Logik kommt in Task 2."""
        return None


def _parse(data):  # pragma: no cover - Stub bis Task 2
    """Stub (Task 1): liefert None. Die echte Parse-Logik kommt in Task 2."""
    return None
