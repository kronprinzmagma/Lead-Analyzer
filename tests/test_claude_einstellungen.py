"""Claude Code darf die gescorten Firmen- und Personendaten nicht lesen (Idee 56).

output/ und cache/ enthalten Abrufe und Bewertungen echter Firmen; sie sind gitignored, liegen aber
lokal im Arbeitsordner. CLAUDE.md importiert AGENTS.md, statt sie zu kopieren (kein Drift).
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_lesesperre_fuer_daten():
    deny = json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))["permissions"]["deny"]
    for regel in ("Read(./output/**)", "Read(./cache/**)"):
        assert regel in deny, regel


def test_claude_md_importiert_agents_md_statt_kopie():
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert re.search(r"^@AGENTS\.md$", claude, re.M)
    # keine zweite Fassung der Spezifikation: die Akzeptanzkriterien stehen nur in AGENTS.md
    assert "AC1" not in claude and "AC11" in agents


def test_definition_of_done_nennt_alle_akzeptanzkriterien():
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    hoechstes = max(int(n) for n in re.findall(r"\*\*AC(\d+) —", agents))
    dod = agents.split("## 7. Definition of Done", 1)[1]
    assert f"AC1–AC{hoechstes}" in dod


def test_coverage_daten_sind_ignoriert():
    assert ".coverage" in (REPO / ".gitignore").read_text(encoding="utf-8").split()
