"""PERF-01 / AC7: Tests für den transparenten Per-URL-JSON-Cache.

Vollständig offline (kein Netz, keine Mocks). Jeder Test lenkt den Cache ZUERST
auf tmp_path (cache.set_cache_dir) — das repo cache/ wird NIE berührt (Pitfall 4).
Die autouse-Fixture _isolate_cache in conftest.py macht das zusätzlich global;
der explizite Aufruf hier dokumentiert die Invariante pro Test.
"""

from __future__ import annotations

from lead_analyzer import cache
from lead_analyzer.models import FetchResult

from conftest import make_fetch_result


# --------------------------------------------------------------------------- #
# Serialisierung: FetchResult <-> dict (round-trip verlustfrei)                #
# --------------------------------------------------------------------------- #

def test_round_trip(tmp_path) -> None:
    """to_dict -> put -> get -> from_dict ergibt das Original (dataclass __eq__)."""
    cache.set_cache_dir(tmp_path)
    fr = make_fetch_result(status=403, ok=False, html=None, error="blockiert")
    key = cache.key_for(["https://x.ch"])
    cache.put(key, fr.to_dict())
    payload = cache.get(key)
    assert payload is not None
    assert FetchResult.from_dict(payload) == fr


def test_from_dict_tolerates_missing_keys(tmp_path) -> None:
    """from_dict mit nur einem Feld wirft nicht — Defaults füllen den Rest."""
    cache.set_cache_dir(tmp_path)
    fr = FetchResult.from_dict({"url": "https://x.ch"})
    assert fr.url == "https://x.ch"
    assert fr.ok is False
    assert fr.headers == {}


# --------------------------------------------------------------------------- #
# Cache-Key: deterministisch, kollisionsarm, FS-sicher                         #
# --------------------------------------------------------------------------- #

def test_key_stability(tmp_path) -> None:
    """Gleiche Kandidaten -> gleicher 64-hex-Key; andere Kandidaten -> anderer Key."""
    cache.set_cache_dir(tmp_path)
    k1 = cache.key_for(["https://x.ch", "http://x.ch"])
    k2 = cache.key_for(["https://x.ch", "http://x.ch"])
    assert k1 == k2                                   # deterministisch
    assert k1 != cache.key_for(["https://y.ch"])      # kollisionsarm
    assert len(k1) == 64                              # sha256-hexdigest
    assert all(c in "0123456789abcdef" for c in k1)   # FS-sicher (kein Traversal)


# --------------------------------------------------------------------------- #
# Robustheit (AC4): korrupte/fehlende Datei + Schema-Mismatch = Miss, kein Crash #
# --------------------------------------------------------------------------- #

def test_corrupt_file_is_a_miss(tmp_path) -> None:
    """Eine kaputte JSON-Datei wird als Miss (None) behandelt — kein Raise."""
    cache.set_cache_dir(tmp_path)
    key = cache.key_for(["https://corrupt.ch"])
    (tmp_path / f"{key}.json").write_text("{ kein json", encoding="utf-8")
    assert cache.get(key) is None


def test_missing_file_is_a_miss(tmp_path) -> None:
    """Ein nie geschriebener Key -> None (klassischer Miss)."""
    cache.set_cache_dir(tmp_path)
    assert cache.get(cache.key_for(["https://never.ch"])) is None


def test_stale_schema_miss(tmp_path) -> None:
    """Gültiges JSON mit fremder schema_version -> Miss (Schema-Bump = Re-Fetch)."""
    import json
    cache.set_cache_dir(tmp_path)
    key = cache.key_for(["https://stale.ch"])
    entry = {"schema_version": 999, "payload": {"url": "https://stale.ch"}}
    (tmp_path / f"{key}.json").write_text(json.dumps(entry), encoding="utf-8")
    assert cache.get(key) is None


# --------------------------------------------------------------------------- #
# Atomarität: kein .tmp-Rest, genau eine {key}.json                            #
# --------------------------------------------------------------------------- #

def test_atomic_no_tempfile_left(tmp_path) -> None:
    """Nach put liegt genau eine {key}.json und KEINE .tmp-Datei im Verzeichnis."""
    cache.set_cache_dir(tmp_path)
    key = cache.key_for(["https://atomic.ch"])
    cache.put(key, make_fetch_result().to_dict())
    files = list(tmp_path.iterdir())
    assert files == [tmp_path / f"{key}.json"]
    assert not any(f.suffix == ".tmp" for f in files)
