"""Laufzeit-Konfiguration.

Ein einzelnes Config-Objekt wird vom CLI gebaut und durch die Pipeline gereicht.
Felder, die erst spätere Phasen nutzen (workers, cache, pagespeed, llm), sind hier
schon angelegt, damit die Signaturen stabil bleiben — Phase 1 nutzt nur einen Teil.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    """Lädt KEY=VALUE-Zeilen aus einer `.env` in os.environ, OHNE bestehende Vars zu überschreiben.

    Winziger stdlib-Parser statt python-dotenv (nicht installiert; zero-new-dep, AC9).
    [CITED: 06-RESEARCH.md "Tiny stdlib .env loader"]

    Verhalten (von tests/test_env_loader.py festgenagelt):
    - Fehlende Datei -> return None, wirft NIE (Robustheit, AC4/AC9).
    - Pro Zeile: strippen; Leerzeilen, Kommentare (`#`) und Zeilen ohne `=` überspringen.
    - `key, _, val = line.partition("=")`; umschliessende " oder ' am Wert strippen.
    - `os.environ.setdefault(key, val)` -> ein real exportierter Var gewinnt immer (T-06-03).
    - Datei-Lesen in try/except OSError -> ein kaputtes File crasht den Start nicht (T-06-04).
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        # utf-8-sig schluckt ein evtl. BOM (Windows-Editoren), sonst würde der
        # erste Key zu "﻿KEY" und der PSI-Key still nicht erkannt (Review M2).
        lines = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        # 'export KEY=val' ist eine gängige .env-Konvention (shell-kompatibel) —
        # das Präfix abschneiden, sonst wird der Key "export KEY" (Review M1).
        if key.startswith(("export ", "export\t")):
            key = key[len("export"):].strip()
        val = val.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, val)   # bestehende Umgebungs-Var NIE überschreiben
    return None


@dataclass
class Config:
    input: str
    output: str
    limit: int | None = None          # nur die ersten N Zeilen verarbeiten (kleiner E2E-Demo-Lauf)
    write_csv: bool = False           # zusätzlich/stattdessen CSV schreiben
    reason_column: bool = True        # optionale Begründungs-Spalte (CLAUDE.md §3 erlaubt)

    # --- ab späteren Phasen relevant; in Phase 1 ungenutzt ---
    workers: int = 8                  # Thread-Pool-Grösse (Phase 5)
    use_cache: bool = True            # Phase 5
    use_pagespeed: bool = True        # Phase 6
    pagespeed_concurrency: int = 2    # Phase 6: PSI-Semaphore-Kappe (< workers, AC8)
    pagespeed_budget: int = 400       # Phase 6: max. PSI-Calls pro Lauf (PERF-02)
    use_zefix: bool = True            # gated via ZEFIX_USER/ZEFIX_PASSWORD presence (Phase 8)
    zefix_concurrency: int = 2        # Semaphore cap (conservative for public-sector API)
    zefix_budget: int = 200           # max Zefix calls per run (PERF-02)
    use_llm: bool = True              # v2 / DIFF-02
    timeout_connect: float = 5.0      # Phase 2
    timeout_read: float = 10.0        # Phase 2
