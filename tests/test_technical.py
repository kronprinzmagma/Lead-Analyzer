"""Phase-3-Tests: reiner Dimension-2-Befund (`analyzers.technical.analyze`).

Deckt BED-02 ab: HTTPS, gültiges SSL und eigene-vs-Gratis-Subdomain. Kein Netz —
`analyze` ist rein über ein `FetchResult` (Signale aus final_url/url-Schema,
ssl_ok, Host). Dim 2 bleibt messbar AUCH ohne Body (html=None): die Signale
stammen nicht aus dem HTML. Nutzt den `make_fetch_result`-Helfer aus conftest.
Stil wie `test_existence.py`.
"""

from __future__ import annotations

import pytest

from lead_analyzer.analyzers import technical
from lead_analyzer.models import DimensionVerdict
from conftest import make_fetch_result


# ---------- HTTPS fehlt -> severe ----------

def test_http_only_is_severe():
    fr = make_fetch_result(final_url="http://firma.ch/")
    v = technical.analyze(fr)
    assert isinstance(v, DimensionVerdict)
    assert v.dim == 2
    assert v.level == "severe"
    assert "HTTPS" in v.reason


# ---------- Ungültiges SSL -> severe ----------

def test_invalid_ssl_is_severe():
    fr = make_fetch_result(final_url="https://firma.ch/", ssl_ok=False)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "severe"
    assert "SSL" in v.reason


def test_unreachable_does_not_fabricate_ssl_signal():
    """P3 (Codex-Review): bei kompletter Nichterreichbarkeit (status None) ist
    ssl_ok=False nur der Default — es darf KEIN 'ungültiges SSL-Zertifikat'
    behauptet werden (keine erfundenen Fakten in der Begründung). Der Dead-Override
    hält den Bedarf trotzdem auf 5; nur die Dim-2-Notiz bleibt ehrlich."""
    fr = make_fetch_result(
        final_url="https://naehatelier-sutter/", ssl_ok=False,
        status=None, ok=False, html=None, error="nicht erreichbar",
    )
    v = technical.analyze(fr)
    assert v.level == "ok"                       # kein Mangel behauptet
    assert "ungültiges SSL" not in v.reason      # kein erfundenes Zertifikat-Faktum (P3)
    assert "gültiges SSL" not in v.reason         # auch KEIN erfundenes 'gültiges SSL' (symmetrisch)
    assert "nicht erreichbar" in v.reason         # ehrlich: nicht messbar
    # Gegenprobe 1: Host hat geantwortet (status gesetzt) + ssl_ok False -> Mangel bleibt.
    fr2 = make_fetch_result(final_url="https://firma.ch/", ssl_ok=False, status=200)
    assert "ungültiges SSL-Zertifikat" in technical.analyze(fr2).reason
    # Gegenprobe 2: erreichter, gesunder Host -> volle ok-Aussage mit 'gültiges SSL'.
    fr3 = make_fetch_result(final_url="https://firma.ch/", ssl_ok=True, status=200)
    assert "gültiges SSL" in technical.analyze(fr3).reason


# ---------- Gratis-Subdomain -> severe ----------

@pytest.mark.parametrize(
    "final_url, marker",
    [
        ("https://kunde.wixsite.com/seite", "wixsite.com"),
        ("https://meinefirma.jimdosite.com/", "jimdosite.com"),
        ("https://user.github.io/", "github.io"),
    ],
)
def test_free_subdomain_is_severe(final_url, marker):
    fr = make_fetch_result(final_url=final_url)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "severe"
    assert marker in v.reason


# ---------- endswith-Guard: evilwix.com ist KEINE Gratis-Subdomain ----------

def test_endswith_guard_own_domain_is_ok():
    fr = make_fetch_result(final_url="https://evilwix.com/", ssl_ok=True)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "ok"


# ---------- www-Strip: trotzdem severe ----------

def test_www_prefix_free_subdomain_is_severe():
    fr = make_fetch_result(final_url="https://www.kunde.wixsite.com/")
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "severe"
    assert "wixsite.com" in v.reason


# ---------- Saubere eigene Domain -> ok ----------

def test_clean_own_domain_is_ok():
    fr = make_fetch_result(final_url="https://firma.ch/", ssl_ok=True)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "ok"


# ---------- NO-BODY: Dim 2 bleibt messbar (html=None) ----------

def test_http_only_still_severe_without_html():
    fr = make_fetch_result(final_url="http://firma.ch/", html=None)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "severe"   # aus dem Schema, NICHT aus dem Body
    assert "HTTPS" in v.reason


def test_clean_domain_still_ok_without_html():
    fr = make_fetch_result(final_url="https://firma.ch/", ssl_ok=True, html=None)
    v = technical.analyze(fr)
    assert v.dim == 2
    assert v.level == "ok"       # kein Neutral-Kurzschluss bei fehlendem HTML


# ---------- dim ist immer 2 ----------

def test_dim_is_always_two():
    for fr in (
        make_fetch_result(final_url="http://firma.ch/"),
        make_fetch_result(final_url="https://firma.ch/", ssl_ok=False),
        make_fetch_result(final_url="https://kunde.wixsite.com/"),
        make_fetch_result(final_url="https://firma.ch/"),
    ):
        assert technical.analyze(fr).dim == 2
