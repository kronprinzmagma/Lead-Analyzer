"""Regressionstest: zwölf erfundene Musterseiten mit festgelegter Gesamtnote (Website-Bedarf).

Die Einzelregel-Tests sichern je eine Regel. Dieser Test sichert das Gesamtergebnis
typischer Seiten: kippt eine Note nach einer Regel- oder Schwellenänderung, zeigt er
genau, welche Musterseite den Platz wechselt und mit welcher Begründung.

- Musterseiten: `tests/musterseiten/*.html`. Alle erfunden (Domains auf `.example`,
  Telefonnummern 0000), damit das öffentliche Repo keine Firmendaten enthält.
- Sollnoten: `tests/musterseiten/sollnoten.toml`. Dort legt Nils die Note fest
  (`quelle = "bestaetigt"`); `quelle = "vorschlag"` heisst: heutige Note, noch nicht bestätigt.
- Offline: der Abruf wird durch das FetchResult aus der TOML-Datei ersetzt, PageSpeed
  und Zefix sind aus. Das Jahr ist auf `STICHJAHR` eingefroren, weil Dimension 6 das
  Copyright-Jahr relativ zum aktuellen Jahr wertet.

Heutige Noten neben den Sollnoten anzeigen (z. B. nach einer Regeländerung):
    python tests/test_musterseiten.py
"""

from __future__ import annotations

import datetime as _dt
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lead_analyzer import pipeline
from lead_analyzer.analyzers import content
from lead_analyzer.config import Config
from lead_analyzer.models import FetchResult, RowRecord

ORDNER = Path(__file__).parent / "musterseiten"
SOLLNOTEN = ORDNER / "sollnoten.toml"
STICHJAHR = 2026
_QUELLEN = {"vorschlag", "bestaetigt"}
NICHT_BEWERTBAR = "nicht bewertbar"   # Sollwert, wenn das Tool keine Note vergeben darf


class _FesteZeit(_dt.datetime):
    """datetime mit eingefrorenem Jahr für den Copyright-Vergleich in Dimension 6."""

    @classmethod
    def now(cls, tz=None):
        return cls(STICHJAHR, 6, 1, tzinfo=tz)


def _seiten() -> list[dict]:
    return tomllib.loads(SOLLNOTEN.read_text(encoding="utf-8"))["seite"]


def _fetch_result(seite: dict) -> FetchResult:
    html = (ORDNER / seite["html"]).read_text(encoding="utf-8") if seite.get("html") else None
    return FetchResult(
        url=seite["url"],
        ok=bool(seite.get("status")) and seite["status"] < 400,
        status=seite.get("status"),
        final_url=seite.get("final_url", seite["url"]),
        redirected=seite.get("final_url", seite["url"]) != seite["url"],
        ssl_ok=seite.get("ssl_ok", True),
        headers={},
        html=html,
        error=seite.get("fehler"),
    )


def bewerte(seite: dict):
    """Bewertet eine Musterseite über die echte Pipeline, mit ersetztem Abruf."""
    fr = _fetch_result(seite)
    alt_fetch, alt_zeit = pipeline.fetch.fetch, content.datetime
    pipeline.fetch.fetch = lambda candidates, config: fr
    content.datetime = _FesteZeit
    try:
        record = RowRecord(0, {"Kundenname": seite["kunde"], "Website": seite["url"]})
        config = Config(input="-", output="-", use_pagespeed=False, use_zefix=False, use_cache=False)
        return pipeline.analyze_row(record, "Website", config)
    finally:
        pipeline.fetch.fetch, content.datetime = alt_fetch, alt_zeit


def test_sollnoten_datei_gueltig():
    """Zwölf Seiten, eindeutige IDs, vorhandene HTML-Dateien, Noten 1..5, bekannte Quelle."""
    seiten = _seiten()
    assert len(seiten) == 12
    ids = [s["id"] for s in seiten]
    assert len(set(ids)) == len(ids)
    for s in seiten:
        assert s["soll_bedarf"] in (*range(1, 6), NICHT_BEWERTBAR), s["id"]
        assert s["quelle"] in _QUELLEN, s["id"]
        if s.get("html"):
            assert (ORDNER / s["html"]).is_file(), s["id"]


@pytest.mark.parametrize("seite", _seiten(), ids=lambda s: s["id"])
def test_musterseite_hat_sollnote(seite):
    res = bewerte(seite)
    ist = NICHT_BEWERTBAR if res.bedarf is None else res.bedarf
    assert ist == seite["soll_bedarf"], (
        f"{seite['id']}: Soll {seite['soll_bedarf']} ({seite['quelle']}), Ist {ist}. "
        f"Begründung: {res.reason}"
    )


if __name__ == "__main__":
    for s in _seiten():
        r = bewerte(s)
        ist = NICHT_BEWERTBAR if r.bedarf is None else r.bedarf
        mark = "" if ist == s["soll_bedarf"] else "  <-- abweichend"
        print(f"{s['id']:<28} soll {s['soll_bedarf']} ({s['quelle']:<10}) ist {ist}{mark}")
        print(f"    {r.reason}")
