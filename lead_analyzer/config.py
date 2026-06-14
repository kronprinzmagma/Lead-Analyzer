"""Laufzeit-Konfiguration.

Ein einzelnes Config-Objekt wird vom CLI gebaut und durch die Pipeline gereicht.
Felder, die erst spätere Phasen nutzen (workers, cache, pagespeed, llm), sind hier
schon angelegt, damit die Signaturen stabil bleiben — Phase 1 nutzt nur einen Teil.
"""

from __future__ import annotations

from dataclasses import dataclass


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
    use_llm: bool = True              # v2 / DIFF-02
    timeout_connect: float = 5.0      # Phase 2
    timeout_read: float = 10.0        # Phase 2
