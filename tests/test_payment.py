"""Offline-RED-Matrix für den Zahlungskräftigkeit-Estimator (Phase 4).

Pinnt den exakten Vertrag der drei Signal-Gruppen A/B/C, der Combine-Map, des
konservativen Defaults und der Pitfall-16-Misfire-Regeln, BEVOR Plan 02 etwas
implementiert (ZK-01/02/03 + AC2/AC3/AC5/AC6). Wave-0-Scaffold: payment.py
existiert noch nicht → der Import schlägt fehl = das gewollte RED-Signal.

Vollständig offline (conftest-Netzsperre bleibt aktiv); kein Test fasst das Netz an.
Stil angelehnt an tests/test_pipeline_bedarf.py.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from lead_analyzer.analyzers import payment          # RED: Modul fehlt bis Plan 02
from lead_analyzer.models import PaymentEstimate, RowRecord


def _rec(name="", branche=""):
    return RowRecord(index=0, cells={"Kundenname": name, "Branche": branche})


def _soup(html):
    return BeautifulSoup(html, "html.parser")


# --------------------------------------------------------------------------- #
# GROUP A — Rechtsform aus dem Firmennamen (wort-begrenzt + case-Regeln)        #
# --------------------------------------------------------------------------- #

def test_legal_form_ag():
    pts, notes = payment._legal_form("Krauer-Sommer AG")
    assert pts == 2
    assert any("AG" in n and "angenommen" in n for n in notes)


def test_legal_form_variants():
    assert payment._legal_form("Muster GmbH")[0] == 1
    assert payment._legal_form("Atelier Sàrl")[0] == 1
    assert payment._legal_form("Foo Sarl")[0] == 1
    assert payment._legal_form("Beispiel SA")[0] == 2
    assert payment._legal_form("Meier & Co")[0] == 1
    assert payment._legal_form("Bau KlG")[0] == 1
    assert payment._legal_form("Hans Müller Einzelfirma")[0] == 0
    # keine Rechtsform-Endung -> 0, keine Notiz
    assert payment._legal_form("Hans Müller") == (0, [])


def test_no_substring_misfire():
    """Pitfall 16 (LOAD-BEARING): vier Misfire-Strings dürfen NIE AG/SA matchen."""
    # "Magazin GmbH": nur GmbH (1 Punkt), NIEMALS AG-Annahme
    pts, notes = payment._legal_form("Magazin GmbH")
    assert pts == 1
    assert not any("AG" in n and "angenommen" in n for n in notes)
    # "Sagi Bau": inneres "agi" trifft \bAG\b nicht -> keine Rechtsform
    assert payment._legal_form("Sagi Bau") == (0, [])
    # "Casa Bella": inneres "asa" trifft \bSA\b nicht -> keine Rechtsform
    assert payment._legal_form("Casa Bella") == (0, [])
    # "Sava Reisen": "Sava" beginnt mit "Sa", aber \bSA\b braucht trailing-Boundary
    assert payment._legal_form("Sava Reisen") == (0, [])
    # kleingeschriebenes "ag"/"sa" im Wort matcht nie (case-sensitiv)
    assert payment._legal_form("flagschiff handel")[0] == 0
    assert payment._legal_form("die saison gmbh")[0] == 1  # nur GmbH (re.I), kein SA
    # "& Co"-False-Positive-Guard: das "co" in "Marco" darf NICHT triggern
    assert payment._legal_form("Marco Bauer") == (0, [])


# --------------------------------------------------------------------------- #
# GROUP B — Branchen-Tier aus record.cells['Branche']                          #
# --------------------------------------------------------------------------- #

def test_branch_tiers():
    # hoch (+2)
    for b in ("Zahnarzt", "Treuhand", "Immobilien", "Garage"):
        pts, notes = payment._branch_tier(b)
        assert pts == 2
        assert any("hoch" in n for n in notes)
    # mittel (+1)
    for b in ("Schreinerei", "Sanitär", "Maler", "Confiserie"):
        pts, notes = payment._branch_tier(b)
        assert pts == 1
        assert any("mittel" in n for n in notes)
    # tief (+0)
    for b in ("Bäckerei", "Coiffeur", "Velo", "Floristik", "Detailhandel"):
        pts, notes = payment._branch_tier(b)
        assert pts == 0
        assert any("tief" in n for n in notes)


def test_branch_missing():
    """Leer/None/unbekannt -> (0, ['Branche unbekannt']); nie raisen, nie raten."""
    for b in ("", None, "Raumfahrt"):
        pts, notes = payment._branch_tier(b)
        assert pts == 0
        assert any("Branche unbekannt" in n for n in notes)


# --------------------------------------------------------------------------- #
# GROUP C — Grössen-Signale aus dem soup                                       #
# --------------------------------------------------------------------------- #

def test_size_signals():
    html_team = '<html><body><a href="/team">Team</a></body></html>'
    pts, notes = payment._size_signals(_soup(html_team))
    assert pts == 1
    assert any("Team" in n for n in notes)

    html_jobs = '<html><body><a href="/karriere">Jobs</a></body></html>'
    pts, notes = payment._size_signals(_soup(html_jobs))
    assert pts == 1
    assert any("Karriere" in n or "Jobs" in n for n in notes)

    html_loc = '<html><body><a href="/standorte">Filialen</a></body></html>'
    pts, notes = payment._size_signals(_soup(html_loc))
    assert pts == 1
    assert any("Standorte" in n for n in notes)

    # alle drei -> Gruppe gedeckelt bei <=2
    html_all = (
        '<html><body>'
        '<a href="/team">Team</a>'
        '<a href="/jobs">Jobs</a>'
        '<a href="/standorte">Standorte</a>'
        '</body></html>'
    )
    pts, notes = payment._size_signals(_soup(html_all))
    assert pts == 2


def test_size_signals_no_html():
    """soup=None -> (0, []) — neutral, NICHT bestraft (Spiegel content.py-Guard)."""
    assert payment._size_signals(None) == (0, [])


# --------------------------------------------------------------------------- #
# COMBINE + DEFAULT + RANGE + DIRECTION                                        #
# --------------------------------------------------------------------------- #

def test_combine_map():
    assert payment._map_to_1_5(4) == 5
    assert payment._map_to_1_5(5) == 5
    assert payment._map_to_1_5(3) == 4
    assert payment._map_to_1_5(2) == 3
    assert payment._map_to_1_5(1) == 2
    assert payment._map_to_1_5(0) == 1
    assert payment._map_to_1_5(-3) == 1


def test_conservative_default():
    """Nichts aufgelöst (kein Suffix, leere Branche, soup=None) -> 2 + dünne Datenlage."""
    est = payment.estimate(_rec("Hans Müller", ""), None, None, None)
    assert est.zahl == 2
    assert "dünne Datenlage" in est.reason


def test_conservative_default_unknown_branche():
    """resolved-predicate-Guard (LOAD-BEARING): unbekannte NICHT-leere Branche.

    'Raumfahrt' erzeugt die ALLEINIGE Notiz ['Branche unbekannt'] -> das ist
    KEINE Auflösung und darf NICHT zu _map_to_1_5(0)==1 kollabieren, sondern muss
    zur konservativen 2 + 'dünne Datenlage' führen.
    """
    est = payment.estimate(_rec("Hans Müller", "Raumfahrt"), None, None, None)
    assert est.zahl == 2
    assert "dünne Datenlage" in est.reason


def test_reason_labelled():
    """ZK-02: reason startswith 'Zahl (Schätzung):' + listet Signale, keine erfundenen Fakten."""
    est = payment.estimate(_rec("Muster AG", "Zahnarzt"), None, None, None)
    assert est.reason.startswith("Zahl (Schätzung):")
    assert est.signals  # mind. ein treibendes Signal
    # keine erfundenen Umsatz-/CHF-Fakten
    assert "CHF" not in est.reason
    assert "Umsatz" not in est.reason


def test_direction_monotone():
    """ZK-03: starker Lead (AG+Zahnarzt+rich soup) >= schwacher (Einzelfirma+Bäckerei)."""
    rich_soup = _soup(
        '<html><body>'
        '<a href="/team">Team</a><a href="/jobs">Jobs</a>'
        '<a href="/standorte">Standorte</a>'
        '</body></html>'
    )
    strong = payment.estimate(_rec("Muster AG", "Zahnarzt"), None, rich_soup, None)
    weak = payment.estimate(_rec("Hans Müller Einzelfirma", "Bäckerei"), None, None, None)
    assert strong.zahl >= weak.zahl
    assert strong.zahl in (4, 5)
    assert weak.zahl in (1, 2)


def test_zahl_range():
    """AC2: zahl ist für jede Eingabe ein int in [1,5]."""
    cases = [
        _rec("Muster AG", "Zahnarzt"),
        _rec("Hans Müller", ""),
        _rec("Atelier Sàrl", "Schreinerei"),
        _rec("", "Bäckerei"),
        _rec("Beispiel SA", "Raumfahrt"),
        _rec("Marco Bauer", "Coiffeur"),
    ]
    for rec in cases:
        est = payment.estimate(rec, None, None, None)
        assert isinstance(est.zahl, int)
        assert 1 <= est.zahl <= 5
