"""Datenträger-Klassen, die durch die Pipeline reisen.

Das wichtigste Detail für AC2 (keine Originalzeile verlieren) ist `index`: er reist
unverändert von Einlesen bis Schreiben mit, damit der stabile Sort nichts verliert
oder verwürfelt und die Original-Zellen 1:1 ausgegeben werden.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RowRecord:
    """Eine Eingabezeile: Originalposition + Original-Zellen in Original-Reihenfolge."""
    index: int                     # Originalposition — geht nie verloren
    cells: dict[str, object]       # geordnet: Spaltenname -> Originalwert (verbatim)


@dataclass
class DimensionVerdict:
    """Teil-Befund einer der sechs Website-Bedarf-Dimensionen (ab Phase 2/3 gefüllt)."""
    dim: int                       # 1..6
    level: str                     # "ok" | "gap" | "severe"
    reason: str                    # menschenlesbar -> Log + Begründungsspalte
    source: str = "html"           # "html" | "pagespeed" | "llm" | "heuristic-fallback"
    dead: bool = False             # explizites Maschinen-Flag: keine/defekte Website -> Bedarf-Override 5
                                   #   (entkoppelt die Score-Richtung vom Anzeige-Text, AC3)


@dataclass
class PaymentEstimate:
    """Zahlungskräftigkeit-Schätzung (AC5: IMMER als Schätzung gekennzeichnet).

    Reines Datenträger-Objekt — die Logik lebt in analyzers/payment.py. `reason`
    ist stets mit "Zahl (Schätzung): " präfixiert; `signals` ist die volle
    Treiberliste fürs Lauf-Log (AC6). [CITED: 04-RESEARCH.md Code Examples]
    """
    zahl: int                 # 1..5, nie leer (AC2/IO-04)
    reason: str               # "Zahl (Schätzung): …" — Begründungsspalte + Log
    signals: list[str] = field(default_factory=list)  # treibende Signale (AC6)


@dataclass
class RowResult:
    """Bewertungsergebnis einer Zeile. Beide Scores sind immer 1..5 (AC2: nie leer)."""
    index: int
    bedarf: int                    # 1..5
    zahl: int                      # 1..5
    reason: str = ""               # Kurzbegründung (Begründungsspalte / Log)
    verdicts: list[DimensionVerdict] = field(default_factory=list)  # für Lauf-Log (AC6/AC11)
    zahl_signals: list[str] = field(default_factory=list)  # Zahlungskräftigkeit-Treiber fürs Lauf-Log (AC6)


@dataclass
class PsResult:
    """PageSpeed-Insights-Resultat (Dim 3, Phase 6) — klein und JSON-serialisierbar.

    Alle Felder sind JSON-native (float|None / bool), damit `__dict__` verlustfrei
    durch `cache.put/get` im PSI-Namespace ("pagespeed-v1") round-trippt (AC7/AC8).
    Wichtig (Degradations-Vertrag, Pitfall 8): ein FEHLER signalisiert sich durch
    `None` als Rückgabe des Clients — NICHT durch `ok=False`. `ok` ist bei einem
    konstruierten Resultat stets True; ein PSI-Fehler/Timeout liefert gar kein
    PsResult, sondern None, und der Analyzer behandelt None wie "nicht versucht".
    [CITED: 06-RESEARCH.md "PsResult dataclass"]
    """
    perf_score: float | None = None   # 0..1 (Lighthouse performance category)
    lcp_ms: float | None = None       # Largest Contentful Paint (ms)
    cls: float | None = None          # Cumulative Layout Shift
    tbt_ms: float | None = None       # Total Blocking Time (ms)
    ok: bool = True                   # immer True bei Konstruktion; None ersetzt "not ok"


@dataclass
class FetchResult:
    """Roh-Fakten eines HTTP-Abrufs (fetch-once-parse-many).

    Trägt alles, was Dimension 1 (Phase 2) UND die späteren Dimensionen 2/4/5/6
    (Phase 3) aus einem einzigen Abruf lesen. Wird in `fetch.fetch()` (Plan 02-02)
    gefüllt; die reinen Analyzer arbeiten offline nur über dieses Objekt.
    """
    url: str                       # die tatsächlich angefragte Variante
    ok: bool                       # True gdw. eine 200–399-Antwort kam
    status: int | None             # HTTP-Status, oder None falls keine Antwort
    final_url: str | None          # response.url nach Redirects
    redirected: bool
    ssl_ok: bool                   # True bei verify=True-Erfolg; False bei Fallback / ohne TLS
    headers: dict                  # Response-Header (für Phase-3-Dimensionen)
    html: str | None               # dekodierter, grössenbegrenzter Body; None falls unerreichbar
    error: str | None              # Notiz-String bei Fehler; None bei Erfolg

    def to_dict(self) -> dict:
        """Serialisiert verlustfrei für den Cache (alle Felder sind JSON-nativ).

        `asdict` ist hier exakt und wartungsfrei — headers ist ein plain dict,
        alle übrigen Felder str/bool/int/None. Gecacht wird das ROHE FetchResult,
        nicht die Scores (Phase-6-Scoring-Änderungen erzwingen so keinen Re-Crawl).
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FetchResult":
        """Rekonstruiert aus einem Cache-dict. Defensiv: fehlende Keys tolerieren,
        damit ein schema-Bump nie KeyError wirft (AC4)."""
        return cls(
            url=d.get("url", ""),
            ok=d.get("ok", False),
            status=d.get("status"),
            final_url=d.get("final_url"),
            redirected=d.get("redirected", False),
            ssl_ok=d.get("ssl_ok", False),
            headers=d.get("headers", {}),
            html=d.get("html"),
            error=d.get("error"),
        )
