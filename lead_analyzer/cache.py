"""Transparenter Per-URL-JSON-Cache (PERF-01 / AC7).

Ein kleiner JSON-File pro URL-Kandidaten-Tupel, keyed per SHA-256. Atomar
geschrieben (tempfile + os.replace) unter einem Modul-Lock — ein abgebrochener
Lauf hinterlässt nie eine truncated Datei und verwirft nicht die bisherige Arbeit
(AC7). Gecacht wird das ROHE FetchResult-dict, nicht die Scores.

Robustheit (AC4): get() wirft NIE — korrupte/fehlende Datei oder Schema-Mismatch
sind ein Miss (None -> Re-Fetch). Der Key ist ein sha256-Hexdigest (nur [0-9a-f]),
damit kein Path-Traversal über den Dateinamen möglich ist (T-05-02).

stdlib only: hashlib, json, os, tempfile, threading, time, pathlib.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path

# Modul-Lock serialisiert konkurrierende put()-Aufrufe (T-05-03, Phase-5-Threads).
_LOCK = threading.Lock()
# Default ./cache; Tests überschreiben das per set_cache_dir(tmp_path) (Pitfall 4).
_CACHE_DIR = Path("cache")
# Schema-Version der Cache-Einträge; ein Bump invalidiert alte Files (Miss).
# 2 (2026-11-23, Idee 40): Seiten-Text wird seit PR #16 anders dekodiert. Einträge mit
# Schema 1 können Zeichensalat oder einen verworfenen Body («Body-Lesefehler») enthalten.
_SCHEMA_VERSION = 2
# Höchstalter eines Eintrags (Idee 41, 2026-11-23): Websites, PageSpeed- und Zefix-Werte
# ändern sich. Ein älterer Eintrag ist ein Miss und wird neu geholt. Gemessen am
# Änderungsdatum der Datei (put() schreibt jede Datei neu). None = kein Ablauf.
DEFAULT_MAX_AGE_DAYS = 30
_MAX_AGE_S: float | None = DEFAULT_MAX_AGE_DAYS * 86400


def set_cache_dir(path) -> None:
    """Setzt das Cache-Verzeichnis (Tests rufen das mit tmp_path)."""
    global _CACHE_DIR
    _CACHE_DIR = Path(path)


def set_max_age_days(days: float | None) -> None:
    """Setzt das Höchstalter in Tagen (CLI --cache-max-age); None = kein Ablauf."""
    global _MAX_AGE_S
    if days is not None and days < 0:
        raise ValueError("Höchstalter muss >= 0 Tage sein")
    _MAX_AGE_S = None if days is None else days * 86400


def key_for(candidates: list[str]) -> str:
    """Deterministischer, FS-sicherer Key über das Kandidaten-Tupel.

    "\\n" trennt die Kandidaten (kommt in URLs nie vor); der sha256-Hexdigest
    ergibt einen 64-stelligen, traversal-sicheren Dateinamen.
    """
    canon = "\n".join(candidates)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def get(key: str) -> dict | None:
    """Liest den gecachten payload oder None. Wirft NIE (AC4).

    Miss-Gründe (alle -> None, Re-Fetch): Datei fehlt, JSON korrupt/truncated,
    OS-Fehler, schema_version passt nicht (Schema-Bump) oder der Eintrag ist
    älter als das Höchstalter.
    """
    try:
        if _MAX_AGE_S is not None and time.time() - _path(key).stat().st_mtime > _MAX_AGE_S:
            return None
        with _path(key).open("r", encoding="utf-8") as f:
            entry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
        return None
    if entry.get("schema_version") != _SCHEMA_VERSION:
        return None
    return entry.get("payload")


def put(key: str, payload: dict) -> None:
    """Schreibt den payload atomar + thread-sicher.

    tempfile.mkstemp im selben Verzeichnis + os.replace -> atomarer same-filesystem
    Rename: ein Leser sieht entweder die alte oder die vollständige neue Datei, nie
    eine halbe. Das Modul-Lock serialisiert Same-Key-Writes (T-05-03).
    [CITED: docs.python.org/3/library/os.html#os.replace — same-filesystem atomic]
    """
    entry = {"schema_version": _SCHEMA_VERSION, "payload": payload}
    with _LOCK:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=_CACHE_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            os.replace(tmp, _path(key))   # atomarer Rename auf demselben Filesystem
        except BaseException:
            # Bei jedem Fehler die temp-Datei aufräumen, nie einen .tmp-Rest lassen.
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
