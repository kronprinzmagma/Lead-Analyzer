"""PERF-03 / AC1: Tests für die parallele run()-Pipeline (ThreadPoolExecutor).

Kerngarantien:
- Determinismus: workers=1-Output == workers=8-Output (Zeile für Zeile).
- Per-Row-Isolation bleibt unter dem Pool erhalten (AC4/ROB-03).
- CLI-Flags --workers / --no-cache sind in die Config verdrahtet.
- Resume (PERF-01/AC7): zweiter Lauf trifft den Cache (_fetch_network 0 zusätzliche Calls).

Determinismus-/Isolations-Tests monkeypatchen fetch.fetch (umgeht Netz UND Cache);
der Resume-Test patcht fetch._fetch_network, damit der echte cache-aside-Pfad läuft.
Jeder cache-berührende Test lenkt den Cache ZUERST auf tmp_path (NIE repo cache/).
"""

from __future__ import annotations

from pathlib import Path

from lead_analyzer import cache, fetch, pipeline, table_io
from lead_analyzer.cli import build_parser
from lead_analyzer.config import Config

from conftest import make_fetch_result

SAMPLE = str(Path(__file__).resolve().parent.parent / "data" / "sample_input.xlsx")


def _read_sheet(path: str):
    """Liest ein Output-Sheet -> (headers, [cells-dict]) für zeilenweisen Vergleich."""
    headers, records = table_io.read_rows(path)
    return headers, [r.cells for r in records]


def test_threaded_equals_sequential(tmp_path, monkeypatch) -> None:
    """workers=1- und workers=8-Output sind Zeile-für-Zeile identisch (Determinismus)."""
    cache.set_cache_dir(tmp_path)
    # fetch.fetch faken: deterministisch, ohne Netz/Cache.
    monkeypatch.setattr(fetch, "fetch", lambda cands, cfg: make_fetch_result(url=cands[0]))

    out1 = str(tmp_path / "seq.xlsx")
    out8 = str(tmp_path / "par.xlsx")
    pipeline.run(Config(input=SAMPLE, output=out1, workers=1))
    pipeline.run(Config(input=SAMPLE, output=out8, workers=8))

    h1, rows1 = _read_sheet(out1)
    h8, rows8 = _read_sheet(out8)
    assert h1 == h8
    assert rows1 == rows8


def test_pool_isolates_bad_row(tmp_path, monkeypatch) -> None:
    """Eine raise'nde Zeile killt den Lauf nicht; alle Zeilen bleiben im Output."""
    cache.set_cache_dir(tmp_path)
    _, in_records = table_io.read_rows(SAMPLE)
    url_col = table_io.detect_url_column(table_io.read_rows(SAMPLE)[0])
    bad_url = None
    for r in in_records:
        raw = r.cells.get(url_col)
        if raw:
            cands = fetch.normalize(raw)
            if cands:
                bad_url = cands[0]
                break
    assert bad_url is not None  # Sample muss mindestens eine gültige URL haben

    def flaky(cands, cfg):
        if cands and cands[0] == bad_url:
            raise RuntimeError("boom")
        return make_fetch_result(url=cands[0] if cands else "")

    monkeypatch.setattr(fetch, "fetch", flaky)
    out = str(tmp_path / "iso.xlsx")
    pipeline.run(Config(input=SAMPLE, output=out, workers=8))

    _, out_rows = _read_sheet(out)
    assert len(out_rows) == len(in_records)        # keine Zeile verloren
    # Die kaputte Zeile bekommt Bedarf 5 + "Fehler:"-Reason.
    bad_rows = [c for c in out_rows if "Fehler:" in str(c.get(table_io.COL_REASON, ""))]
    assert bad_rows, "kaputte Zeile sollte einen Fehler-Reason tragen"
    assert all(int(c[table_io.COL_BEDARF]) == 5 for c in bad_rows)


def test_workers_flag() -> None:
    """--workers N landet im Parser-Namespace."""
    args = build_parser().parse_args(["in.xlsx", "--workers", "3"])
    assert args.workers == 3


def test_no_cache_flag() -> None:
    """--no-cache setzt use_cache=False in der gebauten Config (über main-Pfad-Logik)."""
    args = build_parser().parse_args(["in.xlsx", "--no-cache"])
    assert args.no_cache is True
    cfg = Config(input=args.input, output="x", use_cache=not args.no_cache)
    assert cfg.use_cache is False


def test_resumability_skips_cached(tmp_path, monkeypatch) -> None:
    """Zweiter Lauf trifft den Cache: _fetch_network feuert nicht erneut (AC7)."""
    cache.set_cache_dir(tmp_path)
    calls: list[str] = []

    def spy_network(cands, cfg):
        calls.append(cands[0] if cands else "")
        return make_fetch_result(url=cands[0] if cands else "")

    monkeypatch.setattr(fetch, "_fetch_network", spy_network)
    out = str(tmp_path / "resume.xlsx")
    cfg = Config(input=SAMPLE, output=out, workers=4, use_cache=True)

    pipeline.run(cfg)
    after_first = len(calls)
    assert after_first > 0                          # Lauf 1 hat echt gefetcht

    pipeline.run(cfg)
    assert len(calls) == after_first                # Lauf 2: alles Cache-Hits
