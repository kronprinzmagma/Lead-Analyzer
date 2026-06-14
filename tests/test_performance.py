"""RED-Scaffold (Wave 0): Dim-3-Analyzer `analyzers/performance.py` (BED-03, AC4/AC8).

Definiert das Verhalten des Performance-Analyzers, bevor er existiert — in der
RED-Phase als ImportError erwartet, grün ab Plan 06-03.

Vertrag (06-RESEARCH Pattern 1/2/3):
- Baseline IMMER aus dem viewport-meta-Tag (HTML-Ebene, offline messbar).
- `ps_result is None` (übersprungen ODER Fehler) -> NUR Heuristik, NIE `severe`.
  Das ist der INVERSIONS-GUARD: ein PSI-Fehler darf nie als "langsam" gewertet
  werden (Pitfall 8). `test_psi_error_not_scored_slow` ist der Golden-Test dazu.
- Ein echtes PsResult verfeinert: worst-metric-Band gewinnt; fehlender viewport
  ist mindestens ein `gap`.
- Alle Verdicts: dim == 3.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from lead_analyzer.analyzers import performance

from conftest import make_fetch_result, make_ps_result

# Zwei kleine Soups: mit und ohne viewport-meta.
_HTML_VIEWPORT = (
    '<html><head><meta name="viewport" content="width=device-width">'
    "<title>X</title></head><body>Inhalt</body></html>"
)
_HTML_NO_VIEWPORT = "<html><head><title>X</title></head><body>Inhalt</body></html>"


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def test_viewport_present_no_psi_is_ok():
    """viewport vorhanden + kein PSI -> ok, Heuristik-Fallback, Notiz übersprungen/Fehler."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    v = performance.analyze(fr, _soup(_HTML_VIEWPORT), None)
    assert v.dim == 3
    assert v.level == "ok"
    assert "heuristic-fallback" in v.source
    assert ("übersprungen" in v.reason) or ("Fehler" in v.reason)


def test_no_viewport_no_psi_is_gap():
    """kein viewport + kein PSI -> gap (HTML-Heuristik)."""
    fr = make_fetch_result(html=_HTML_NO_VIEWPORT)
    v = performance.analyze(fr, _soup(_HTML_NO_VIEWPORT), None)
    assert v.dim == 3
    assert v.level == "gap"


def test_psi_error_not_scored_slow():
    """GOLDEN / Inversions-Guard: ps_result=None -> ok, ausdrücklich NICHT severe (Pitfall 8)."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    v = performance.analyze(fr, _soup(_HTML_VIEWPORT), ps_result=None)
    assert v.dim == 3
    assert v.level != "severe"     # ein PSI-Fehler ist NIE "langsam"
    assert v.level == "ok"


def test_psi_low_perf_severe():
    """Echtes PsResult mit perf<0.5 -> severe, source=pagespeed."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    v = performance.analyze(fr, _soup(_HTML_VIEWPORT), make_ps_result(perf_score=0.30))
    assert v.dim == 3
    assert v.level == "severe"
    assert v.source == "pagespeed"


def test_psi_good_perf_ok():
    """Echtes PsResult mit perf>=0.9 + viewport -> ok, source=pagespeed."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    v = performance.analyze(fr, _soup(_HTML_VIEWPORT), make_ps_result(perf_score=0.95))
    assert v.dim == 3
    assert v.level == "ok"
    assert v.source == "pagespeed"


def test_worst_metric_band():
    """Gute perf, aber LCP=5000 (severe) -> severe (worst metric wins)."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    v = performance.analyze(
        fr, _soup(_HTML_VIEWPORT), make_ps_result(perf_score=0.95, lcp_ms=5000)
    )
    assert v.dim == 3
    assert v.level == "severe"


def test_psi_good_but_no_viewport_at_least_gap():
    """Gute PSI-Werte aber kein viewport -> mindestens gap, nicht ok."""
    fr = make_fetch_result(html=_HTML_NO_VIEWPORT)
    v = performance.analyze(
        fr, _soup(_HTML_NO_VIEWPORT), make_ps_result(perf_score=0.95)
    )
    assert v.dim == 3
    assert v.level in ("gap", "severe")
    assert v.level != "ok"


def test_all_verdicts_are_dim_3():
    """Über alle Pfade hinweg ist dim immer 3."""
    fr = make_fetch_result(html=_HTML_VIEWPORT)
    for ps in (None, make_ps_result(perf_score=0.30), make_ps_result(perf_score=0.95)):
        assert performance.analyze(fr, _soup(_HTML_VIEWPORT), ps).dim == 3
