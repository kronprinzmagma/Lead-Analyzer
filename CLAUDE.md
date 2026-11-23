# CLAUDE.md — Lead-Analyzer

Spezifikation, Akzeptanzkriterien und Arbeitsweise stehen in AGENTS.md (eine Quelle für Codex und
Claude Code, darum Import statt Kopie: https://code.claude.com/docs/en/memory#agents-md).

@AGENTS.md

## Prüfbefehle (dieselben wie die CI, `.github/workflows/test.yml`)

```bash
uv sync --locked
uv run ruff check .
uv run pytest tests/ -q --cov --cov-report=term-missing   # Untergrenze 90 % in pyproject.toml
```

## Datensperre

`output/` und `cache/` enthalten gescorte Firmen- und Personendaten, `.env` die API-Schlüssel. Claude Code
liest sie nicht: `.claude/settings.json` sperrt sie (`deny`). Eine Ablehnung wird nicht umgangen, auch nicht
über die Shell (`cat`, `head`, Python). Für Tests synthetische Daten unter `tests/` verwenden.
