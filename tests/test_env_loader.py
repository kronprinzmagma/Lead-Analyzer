"""RED-Scaffold (Wave 0): stdlib `.env`-Loader (AC9, T-06-03/04).

Diese Tests definieren das exakte Verhalten von `lead_analyzer.config.load_dotenv`,
bevor er existiert — sie sind in der RED-Phase als Fehlschlag (ImportError /
AttributeError) erwartet und werden durch Plan 06-02 grün.

Kernverträge:
- KEY=VALUE wird geparst; Kommentare (`#`), Leerzeilen und Zeilen ohne `=` ignoriert.
- Umschliessende Anführungszeichen (" oder ') werden gestrippt.
- `setdefault`-Semantik: ein bereits gesetzter Env-Var wird NIE überschrieben.
- Eine fehlende Datei -> None, ohne jede Exception (Robustheit, AC4/AC9).

Alle Tests isolieren os.environ via monkeypatch und schreiben die .env nach tmp_path,
damit nichts in die echte Umgebung leckt.
"""

from __future__ import annotations

import os

from lead_analyzer.config import load_dotenv


def test_parses_keyvalue_ignores_comments_blank_and_strips_quotes(tmp_path, monkeypatch):
    """KEY=value, # comment, Leerzeile, QUOTED="val", SINGLE='val' -> korrekt geladen."""
    env = tmp_path / ".env"
    env.write_text(
        "# das ist ein Kommentar\n"
        "KEY=value\n"
        "\n"
        '   # eingerückter Kommentar\n'
        'QUOTED="val"\n'
        "SINGLE='val'\n",
        encoding="utf-8",
    )
    # Saubere Ausgangslage — keiner der Keys ist vorab gesetzt.
    for k in ("KEY", "QUOTED", "SINGLE"):
        monkeypatch.delenv(k, raising=False)

    result = load_dotenv(str(env))

    assert result is None                         # Loader gibt nichts zurück
    assert os.environ["KEY"] == "value"
    assert os.environ["QUOTED"] == "val"          # doppelte Quotes gestrippt
    assert os.environ["SINGLE"] == "val"          # einfache Quotes gestrippt


def test_does_not_override_existing_env_var(tmp_path, monkeypatch):
    """setdefault-Semantik: ein real exportierter Var gewinnt immer über die Datei (T-06-03)."""
    monkeypatch.setenv("PRESET", "real")          # bereits gesetzt
    env = tmp_path / ".env"
    env.write_text("PRESET=fromfile\n", encoding="utf-8")

    load_dotenv(str(env))

    assert os.environ["PRESET"] == "real"         # NICHT überschrieben


def test_missing_file_returns_none_and_does_not_raise(tmp_path):
    """Fehlende .env -> None, keine Exception (AC9/AC4)."""
    missing = tmp_path / "gibtsnicht.env"
    assert not missing.exists()
    # Darf NICHT werfen.
    assert load_dotenv(str(missing)) is None


def test_line_without_equals_is_ignored(tmp_path, monkeypatch):
    """Eine Zeile ohne `=` wird stillschweigend übersprungen (T-06-04, kein Crash)."""
    env = tmp_path / ".env"
    env.write_text("DASisteinemuellzeile\nGUT=ja\n", encoding="utf-8")
    monkeypatch.delenv("GUT", raising=False)

    load_dotenv(str(env))

    assert os.environ["GUT"] == "ja"
