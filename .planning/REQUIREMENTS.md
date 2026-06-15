# REQUIREMENTS — Lead-Analyzer

Quelle der Wahrheit: `CLAUDE.md` (bindende Akzeptanzkriterien AC1–AC11) + `docs/scoring_website_bedarf.md`. Diese Datei übersetzt sie in testbare, atomare REQ-IDs und verknüpft jede mit ihrem AC. v1 = das, was die Definition of Done (CLAUDE.md §7) verlangt.

## v1 Requirements

### IO — Ein-/Ausgabe & Bedienung
- [x] **IO-01**: Nutzer kann eine `.xlsx`- oder `.csv`-Datei als Eingabe übergeben; das Tool liest alle Zeilen und Spalten ein. *(AC1, AC9)*
- [x] **IO-02**: Das Tool erkennt die URL-Spalte tolerant (Namensvarianten «URL», «Website», «Webseite», «Web», …); fehlt eine erkennbare URL-Spalte → klare Fehlermeldung statt Absturz. *(AC2, AC4)*
- [x] **IO-03**: Die Ausgabe enthält **alle Original-Spalten unverändert** (Werte, Reihenfolge) plus genau zwei neue Spalten `Website-Bedarf (1-5)` und `Zahlungskräftigkeit (1-5)`. *(AC2)*
- [x] **IO-04**: Beide Score-Spalten sind ganzzahlig 1–5 und nie leer (jede Eingabezeile bekommt beide Scores). *(AC2)*
- [x] **IO-05**: Die Ausgabe ist absteigend sortiert zuerst nach `Website-Bedarf`, dann nach `Zahlungskräftigkeit`; dabei geht keine Originalzeile verloren (`len(out) == len(in)`). *(AC2)*
- [x] **IO-06**: Ausgabe wird als `.xlsx` geschrieben (CSV zusätzlich erlaubt); mindestens sichtbar: Kundenname, URL, beide Scores. *(AC2)*
- [x] **IO-07**: Ein einziger Einstiegspunkt/Befehl: Eingabedatei rein → Ausgabedatei raus, ohne Eingriff pro Zeile. *(AC1, AC9)*

### BED — Website-Bedarf-Score (6 Dimensionen)
- [x] **BED-01**: Dimension 1 *Existenz & Substanz* wird real gemessen: erreichbar (HTTP 200 nach http/https- und www-Varianten-Probe), geparkt/Platzhalter, Social-Media-only, leerer Inhalt. *(AC11, AC3)*
- [x] **BED-02**: Dimension 2 *Technische Basis* wird real gemessen: HTTPS + gültiges SSL-Zertifikat; eigene Domain vs. Gratis-Subdomain (wixsite, jimdosite, business.site, …). *(AC11, AC3)*
- [x] **BED-03**: Dimension 3 *Mobile & Performance* wird gemessen: Viewport-Meta (immer) + PageSpeed/Lighthouse-Performance wenn verfügbar; sonst heuristischer Fallback mit Vermerk. *(AC11, AC8)*
- [x] **BED-04**: Dimension 4 *Auffindbarkeit (SEO)* wird real gemessen: Title/Meta-Description (Vorhandensein+Länge), Canonical, robots.txt/sitemap.xml, H1, noindex. *(AC11, AC3)*
- [x] **BED-05**: Dimension 5 *KI-/Answer-Engine-Bereitschaft* wird mind. heuristisch gemessen: JSON-LD/Schema.org, Open-Graph-Tags, Microdata. *(AC11)*
- [x] **BED-06**: Dimension 6 *Inhalt, Aktualität & Conversion* wird mind. heuristisch gemessen: Kontaktformular, `tel:`/`mailto:`, Impressum, Copyright-Jahr/Generator als Aktualitäts-Proxy. *(AC11)*
- [x] **BED-07**: Die 6 Dimensions-Befunde werden deterministisch zum 1–5-Score aggregiert gemäss Banddefinition in `docs/scoring_website_bedarf.md`; «keine erreichbare Website» überschreibt immer auf 5. *(AC3, AC11)*
- [x] **BED-08**: Score-Richtung ist monoton korrekt: mehr/grössere Lücken ⇒ höherer Bedarf (per Richtungs-Tests abgesichert). *(AC3)*

### ZK — Zahlungskräftigkeit-Score
- [x] **ZK-01**: Pro Kunde wird ein 1–5-Score aus öffentlichen Signalen geschätzt: Rechtsform aus Firmenname (AG/GmbH/Einzelfirma), Branchen-Kaufkraft-Tier, Website-Grössensignale (mehrere Standorte/Team/Karriere). *(AC5)*
- [x] **ZK-02**: Jede Schätzung ist als Schätzung gekennzeichnet und ihre Signale/Annahmen sind nachvollziehbar (Begründungsspalte und/oder Log); keine erfundenen Fakten — fehlt Datenlage, konservativ schätzen + kennzeichnen. *(AC5)*
- [x] **ZK-03**: Score-Richtung korrekt: höher = mehr Kaufkraft. *(AC3)*

### ROB — Robustheit
- [x] **ROB-01**: Leere URL, ungültige/kaputte URL (`htp://…`), nicht erreichbare Seite, Timeout, geparkte Domain, Social-only führen **nie** zum Absturz; jede solche Zeile erhält einen sinnvollen Score (bei «keine Website» = Bedarf 5) + Vermerk. *(AC4)*
- [x] **ROB-02**: HTTP-Abruf hat harte Timeouts, browser-ähnlichen User-Agent, Redirect-/Grössen-Limit, toleranten Encoding-Fallback; SSL-Fehler wird zum Dim-2-Signal, nicht zum Crash. *(AC4)*
- [x] **ROB-03**: Eine fehlerhafte Zeile/Stage isoliert (per-row Exception-Boundary); der Gesamtlauf läuft weiter. *(AC1, AC4)*

### NACH — Nachvollziehbarkeit
- [x] **NACH-01**: Zu jedem Kunden ist erkennbar, welche Signale/Dimensionen den Bedarf-Score und welche Annahmen den Zahlungskräftigkeit-Score getrieben haben — über eine Begründungsspalte im Output und/oder ein Lauf-Log. *(AC6, AC5, AC11)*

### PERF — Wiederholbarkeit, Cache, Limits
- [x] **PERF-01**: Ergebnisse pro URL werden inkrementell auf Platte gecacht (atomic write); ein erneuter Lauf nutzt den Cache, ein Abbruch verwirft nicht die ganze Arbeit. *(AC7)*
- [x] **PERF-02**: Externe APIs (PageSpeed, optional LLM/Zefix) nutzen Batching/Retry/Backoff und respektieren Rate-Limits/`Retry-After`; ein API-Fehler bricht den Lauf nicht ab. *(AC8)*
- [x] **PERF-03**: Hunderte Zeilen werden in vertretbarer Zeit verarbeitet (nebenläufiger Fetch, optionale Stages skippbar via Flag). *(AC1)*

### SETUP — Setup, Docs, Verifikation
- [x] **SETUP-01**: README erklärt Setup (inkl. API-Keys via `.env`) und Aufruf in <5 Minuten; läuft auch ganz ohne Keys (graceful degradation). *(AC9)*
- [x] **SETUP-02**: Lauffähig gegen `data/sample_input.xlsx`; die Edge-Cases (leere URL Kiosk, kaputte URL Nähatelier, grosse vs. kleine Firma) werden plausibel bewertet, mit kurzer Begründung warum die Beispiel-Scores sinnvoll sind. *(AC10)*
- [x] **SETUP-03**: `.env` und Ausgaben werden nicht committet (.gitignore); Tool arbeitet lokal. *(CLAUDE.md §6)*

## v2 / Differentiators (deferred)
- [x] **DIFF-01**: Live-Zefix-Lookup (Handelsregister) zur Anreicherung der Zahlungskräftigkeit — autoritative Rechtsform + Status + Sitz statt Namens-Heuristik; gated über `ZEFIX_USER`/`ZEFIX_PASSWORD` (ohne Creds byte-identisch zum Offline-Lauf). **→ Phase 8 (aktiviert).** *(verschärft ZK-01, erfüllt AC5 vollständig)*
- [ ] **DIFF-02**: LLM-Layer für qualitative Bewertung von Dimension 6 (Textqualität/Aktualität) — nur additiv, nur wenn Key vorhanden.
- [ ] **DIFF-03**: Konfigurierbare Branchen→Tier-Tabelle, damit Sales Gewichte überschreiben kann.

## Out of Scope
- Dashboard / Web-Frontend — CLAUDE.md §6 (CLI-Skript, Excel rein/raus).
- Dauerbetrieb / Cron / Salesforce-Integration — §6.
- Bonitäts-Audit mit echten Finanzdaten — Zahlungskräftigkeit ist explizit nachvollziehbare Schätzung (AC5).
- Veröffentlichung von Firmen-/Personendaten — §6 (lokal arbeiten).

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IO-01 | Phase 1 | Done |
| IO-02 | Phase 1 | Done |
| IO-03 | Phase 1 | Done |
| IO-04 | Phase 1 | Done |
| IO-05 | Phase 1 | Done |
| IO-06 | Phase 1 | Done |
| IO-07 | Phase 1 | Done |
| BED-01 | Phase 2 | Done |
| ROB-01 | Phase 2 | Done |
| ROB-02 | Phase 2 | Done |
| ROB-03 | Phase 2 | Done |
| BED-02 | Phase 3 | Done |
| BED-04 | Phase 3 | Done |
| BED-05 | Phase 3 | Done |
| BED-06 | Phase 3 | Done |
| BED-07 | Phase 3 | Done |
| BED-08 | Phase 3 | Done |
| NACH-01 | Phase 3 | Done |
| ZK-01 | Phase 4 | Done |
| ZK-02 | Phase 4 | Done |
| ZK-03 | Phase 4 | Done |
| PERF-01 | Phase 5 | Done |
| PERF-03 | Phase 5 | Done |
| BED-03 | Phase 6 | Done |
| PERF-02 | Phase 6 | Done |
| SETUP-01 | Phase 7 | Done |
| SETUP-02 | Phase 7 | Done |
| SETUP-03 | Phase 7 | Done |
| DIFF-01 | Phase 8 | Done |

**Coverage:** 28/28 v1 requirements mapped. DIFF-01 activated and mapped to Phase 8 (fully satisfies AC5 via authoritative Zefix lookup); DIFF-02/DIFF-03 deliberately unmapped (deferred).
