# MyWEBSITE Lead-Analyzer

Lädt eine **Excel-/CSV-Tabelle mit Kunden** (eine Spalte enthält die Website-URL) und gibt
**dieselbe Tabelle** zurück — ergänzt um zwei ganzzahlige Score-Spalten `Website-Bedarf (1-5)`
und `Zahlungskräftigkeit (1-5)` plus eine optionale `Begründung`-Spalte. Die Ausgabe ist
**absteigend sortiert** zuerst nach Website-Bedarf, dann nach Zahlungskräftigkeit, sodass die
**idealen Leads (hoher Bedarf UND hohe Kaufkraft) zuoberst** stehen. Das Tool ist ein CLI-Skript:
eine Datei rein, eine Datei raus — kein Frontend, kein Dauerbetrieb.

## Setup (unter 5 Minuten)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Laufzeit-Abhängigkeiten: `openpyxl`, `requests`, `beautifulsoup4`. **Keine API-Keys nötig.**

## Ausführen

Ein einziger Befehl — Eingabedatei rein, Ausgabedatei raus:

```bash
python run.py data/sample_input.xlsx -o output/leads.xlsx
```

Die Ausgabe landet unter dem mit `-o` angegebenen Pfad (Default: `output/leads_scored.xlsx`).

## CLI-Flags

| Flag | Bedeutung |
|------|-----------|
| `input` (Positional) | Eingabedatei (`.xlsx` oder `.csv`) mit einer URL-Spalte |
| `-o`, `--output` | Ausgabedatei (`.xlsx`; `.csv` möglich). Default: `output/leads_scored.xlsx` |
| `-n`, `--limit N` | Nur die ersten N Zeilen verarbeiten (kleiner Demo-Lauf) |
| `--csv` | Zusätzlich/als CSV ausgeben |
| `--no-reason` | Begründungs-Spalte weglassen (nur die zwei Score-Spalten) |
| `--workers N` | Anzahl paralleler Fetch-Threads (Default: 8) |
| `--no-cache` | Cache komplett umgehen (kein Lesen, kein Schreiben) |
| `--no-pagespeed` | PageSpeed-Anreicherung von Dim 3 abschalten (erzwingt Heuristik) |

## API-Keys / `.env` (alle optional)

Das Tool **läuft vollständig OHNE jeden API-Key** (graceful degradation). Keys verbessern nur,
sie sind nie Voraussetzung.

```bash
cp .env.example .env        # Keys eintragen, falls vorhanden — .env wird NICHT committet
```

- **`PAGESPEED_API_KEY`** — reichert Dimension 3 (Mobile & Performance) mit echten Core Web
  Vitals aus der Google-PageSpeed-Insights-API an. Ohne diesen Key ist der PageSpeed-Tier
  schlicht **aus** und Dim 3 fällt auf die Viewport-Heuristik zurück. Einen kostenlosen Key
  gibt es in der Google Cloud Console (PageSpeed Insights API aktivieren → API-Key erstellen).
- **`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`** — reserviert für den zurückgestellten LLM-Layer;
  in v1 **nicht genutzt**.

## Re-Run & Cache

Ergebnisse werden **pro URL auf der Festplatte gecacht** (`cache/`). Ein erneuter Lauf
überspringt bereits analysierte URLs — ein abgebrochener Lauf verwirft also nicht die ganze
Arbeit. Mit `--no-cache` wird der Cache komplett umgangen. Die Parallelität steuerst du über
`--workers` (Default 8).

## Datenschutz

`.env`, `output/` und `cache/` sind gitignored und werden **nie committet**. Das Tool arbeitet
lokal; es werden keine Personen-/Firmendaten veröffentlicht.

## Tests

```bash
python -m pytest tests/ -q
```

202 Tests, alle grün. `pytest` ist nur für die Entwicklung nötig (nicht im Laufzeit-`requirements.txt`).
