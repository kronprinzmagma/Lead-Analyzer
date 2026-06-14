# Lead-Analyzer

## What This Is

Ein lauffähiges CLI-Tool für Nils (Product Owner) und das Sales-/Vertriebsteam. Eingabe ist eine Excel-/CSV-Kundenliste mit einer Website-URL pro Kunde; Ausgabe ist dieselbe Tabelle plus zwei numerische Bewertungs-Spalten pro Kunde: **Website-Bedarf (1–5)** und **Zahlungskräftigkeit (1–5)**. Damit sieht Sales auf einen Blick, welche Kunden eine neue, moderne Website dringend brauchen UND die Kaufkraft mitbringen.

## Core Value

Aus einer rohen Kundenliste pro Zeile zwei nachvollziehbare, sortierbare Scores erzeugen — die idealen Leads (hoher Bedarf **und** hohe Zahlungskräftigkeit) stehen zuoberst. Excel rein → Excel raus, ohne manuelles Eingreifen pro Zeile.

## Requirements

### Validated

(None yet — ship to validate)

### Active

<!-- Bindende Akzeptanzkriterien aus CLAUDE.md. REQ-IDs in REQUIREMENTS.md. -->

- [ ] AC1 — Ganze Liste verarbeiten (hunderte Zeilen), keine Stichprobe, kein Eingriff pro Zeile
- [ ] AC2 — Output = alle Original-Spalten unverändert + genau 2 Score-Spalten (1–5, ganzzahlig, keine leeren Scores)
- [ ] AC3 — Score-Richtung exakt nach Definition (höher = mehr Bedarf bzw. mehr Kaufkraft)
- [ ] AC4 — Robustheit: ungültige/fehlende/nicht erreichbare URL, Timeout, geparkt, Social-only → kein Absturz, sinnvoller Score + Vermerk
- [ ] AC5 — Zahlungskräftigkeit pro Kunde aus öffentlichen Quellen recherchiert/geschätzt, Quelle/Annahme nachvollziehbar, keine erfundenen Fakten
- [ ] AC6 — Nachvollziehbarkeit: je Score erkennbar, welche Signale ihn trieben (mind. Lauf-Log)
- [ ] AC7 — Wiederholbar & resümierbar: Cache, Abbruch verwirft nicht alle Arbeit
- [ ] AC8 — Externe APIs mit Batching/Retry/Backoff (Rate-Limits ≠ Abbruch)
- [ ] AC9 — Ein Einstiegspunkt: Datei rein → Datei raus; README erklärt Setup (.env) + Aufruf in <5 Min
- [ ] AC10 — Lauffähig gegen data/sample_input.xlsx; Edge-Cases plausibel; Beispiel-Scores begründet
- [ ] AC11 — Website-Bedarf aus 6 Dimensionen (nicht Bauchnote); Dim. 1–4 real gemessen, 5/6 mind. heuristisch; je Kunde nachvollziehbar

### Out of Scope

- Dashboard / Web-Frontend — CLAUDE.md §6: Tool ist ein CLI-Skript, Excel rein/raus.
- Dauerbetrieb / Cron / Salesforce-Integration — §6 Scope-Schutz.
- Veröffentlichung von Personen-/Firmendaten — §6: lokal arbeiten, .env + Ausgaben nicht committen.
- Perfekte Firmen-Finanzdaten — Zahlungskräftigkeit ist explizit eine nachvollziehbare *Schätzung*, kein Bonitäts-Audit.

## Context

- **Spezifikation:** `CLAUDE.md` (bindende AC1–AC11) und `docs/scoring_website_bedarf.md` (6-Dimensionen-Rubrik). Diese sind die Quelle der Wahrheit, nicht dieses Dokument.
- **Beispieldaten:** `data/sample_input.xlsx` — 42 Schweizer KMU (Maler, Schreiner, Garage, Gartenbau, Bäckerei, Zahnarzt, Treuhand, Coiffeur, Velo, Immobilien, Sanitär, Floristik …). Spalten: Kundennummer, Kundenname, Branche, Ort, Website. Zwei Edge-Cases am Ende: Zeile mit leerer URL (Kiosk), Zeile mit kaputter URL `htp://naehatelier-sutter` (Nähatelier).
- **Domäne:** Schweizer KMU. Rechtsform aus Firmenname ableitbar (AG/GmbH/Einzelfirma); öffentliche Quellen u.a. Zefix (Handelsregister), Website selbst (Standorte/Team/Impressum).
- **Versprechen eines modernen Website-Produkts** (eigene Domain, SSL, Responsive, SEO, KI-Sichtbarkeit, aktuelle Inhalte) = genau die Lücken, die der Bedarf-Score misst.

## Constraints

- **Tech stack**: Python 3 + CLI. venv vorhanden unter `.venv` (openpyxl, requests, beautifulsoup4 installiert). Excel via openpyxl, kein pandas nötig.
- **Netz/APIs**: Graceful degradation. Kern = Live-HTTP-Abruf + HTML-Parse. PageSpeed-Insights-API optional (keyless mit striktem Limit, besser mit `PAGESPEED_API_KEY`). LLM-Layer optional (nur wenn `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` gesetzt). Ohne Netz/Keys → Heuristik-Fallback mit Vermerk.
- **Robustheit**: jede Zeile muss einen Score bekommen, auch bei Fehlern (AC4). Kein Absturz bei einer einzelnen kaputten URL.
- **Privacy**: `.env` und Ausgaben nicht committen (.gitignore deckt das ab). Lokal arbeiten.
- **Bedienung**: ein Befehl, README < 5 Min Setup.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + openpyxl/requests/bs4 | Excel-I/O + HTTP + HTML-Parse pragmatisch, venv schon aufgesetzt | — Pending |
| Graceful degradation statt harter API-Pflicht | User hat keine Key-Präferenz; AC4 verlangt Robustheit; Tool muss in <5 Min ohne Setup-Hürde laufen | — Pending |
| Zahlungskräftigkeit primär heuristisch (Rechtsform + Branche + Website-Signale), LLM/Zefix optional | AC5 erlaubt nachvollziehbare Schätzung; keine harte Abhängigkeit von externer DB | — Pending |
| Begründungs-Spalte(n) im Output + Lauf-Log | erfüllt AC5/AC6/AC11 Nachvollziehbarkeit direkt im Liefergegenstand | — Pending |
| JSON-Cache pro URL | erfüllt AC7 (resümierbar) + AC8 (vermeidet doppelte API-Calls) | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-14 after initialization*
