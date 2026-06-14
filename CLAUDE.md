# CLAUDE.md — Lead-Analyzer

Diese Datei ist die verbindliche Spezifikation für Claude Code. **Bindend sind die Akzeptanzkriterien (Abschnitt 4).** Den Lösungsweg (Sprache, Libraries, Architektur, ob LLM oder Heuristik) wählst du selbst — Hauptsache, die Akzeptanzkriterien sind erfüllt.

## 1. Ziel

Ich (Nils, Product Owner) lade eine Excel-/CSV-Tabelle mit Kunden hoch, in der u.a. eine **Website-URL** steht. Das Tool gibt dieselbe Tabelle zurück, ergänzt um **zwei Bewertungs-Spalten pro Kunde**:

1. **Website-Bedarf (1–5)** — wie dringend dieser Kunde eine moderne, professionelle Website braucht.
2. **Zahlungskräftigkeit (1–5)** — wie kaufkräftig / wirtschaftlich stark der Kunde ist (lohnt sich der Verkauf).

Hintergrund: Sales soll aus einer Kundenliste schnell sehen, **wer eine neue Website nötig hat UND die nötige Kaufkraft mitbringt**. Mehr braucht der Output nicht.

## 2. Eingabe

- Eine Excel- (`.xlsx`) oder CSV-Datei mit einer Zeile pro Kunde.
- Mindestens eine Spalte enthält eine **URL** (Spaltenname tolerant erkennen: «URL», «Website», «Webseite», «Web», o.ä.). Fehlt eine erkennbare URL-Spalte → klare Fehlermeldung.
- Weitere Spalten (Kundenname, Ort, Branche, Umsatz, …) können vorhanden sein, müssen aber nicht. Sie werden **unverändert durchgereicht**.
- Beispiel-Datei liegt unter `data/sample_input.xlsx`.

## 3. Ausgabe

- Dieselbe Tabelle (alle Original-Spalten unverändert) **plus** zwei neue Spalten:
  - `Website-Bedarf (1-5)`
  - `Zahlungskräftigkeit (1-5)`
- **Mindestens sichtbar** müssen sein: Kundenname, URL, `Website-Bedarf (1-5)`, `Zahlungskräftigkeit (1-5)`. Die zwei Score-Spalten sind die wichtigsten.
- **Beide Scores numerisch** (ganze Zahl 1–5), damit nach ihnen sortiert/gefiltert werden kann.
- **Standard-Sortierung der Ausgabe:** absteigend zuerst nach `Website-Bedarf`, dann nach `Zahlungskräftigkeit` — so stehen Kunden mit **hohem Bedarf UND hoher Zahlungskräftigkeit zuoberst** (die idealen Leads). Sortierung soll im Output nicht die Originalzeilen verlieren.
- Format: `.xlsx` (CSV zusätzlich erlaubt).
- Eine optionale dritte Spalte mit Kurzbegründung/Quelle je Kunde ist erlaubt, aber nicht Pflicht (hilft der Nachvollziehbarkeit).

### Score-Definitionen (Richtung eindeutig)

**Website-Bedarf (1–5)** — höher = grösserer Bedarf = besserer Lead. **Wird aus sechs messbaren Dimensionen abgeleitet, nicht als Bauchnote.** Vollständige Rubrik (Dimensionen, Mess-Signale, Produkt-Bezug, Aggregation, Edge-Cases): siehe **[`docs/scoring_website_bedarf.md`](docs/scoring_website_bedarf.md)**.

Die sechs Dimensionen (jede aus einem Versprechen eines modernen Website-Produkts = Kundenlücke abgeleitet):

1. **Existenz & Substanz** — erreichbar? geparkt? nur Social-Media?
2. **Technische Basis** — HTTPS/SSL, eigene Domain vs. Gratis-Subdomain.
3. **Mobile & Performance** — responsive, Core Web Vitals (PageSpeed-Insights-API).
4. **Auffindbarkeit (SEO)** — Title/Meta, Canonical, robots/sitemap, Indexierbarkeit.
5. **KI-/Answer-Engine-Bereitschaft** — strukturiertes Markup (Schema.org/JSON-LD), OG-Tags.
6. **Inhalt, Aktualität & Conversion** — Kontaktformular/`tel:`/`mailto:`, Impressum, Aktualitäts-Proxy (Copyright/Generator).

Aggregation: **5** = keine/defekte Website ODER schwere Mängel über mehrere Dimensionen · **4** = mehrere klare Lücken · **3** = spürbare Lücken in 1–2 Dimensionen · **2** = solide, kleine Schwächen · **1** = modern über alle Dimensionen. «Keine erreichbare Website» überschreibt immer auf 5.

**Zahlungskräftigkeit (1–5)** — höher = mehr Kaufkraft / lohnender:
- **5** = wirtschaftlich stark (z.B. AG mit substanziellem Kapital, mehrere Standorte/Mitarbeitende, kaufkräftige Branche).
- **3** = solider KMU-Mittelstand.
- **1** = geringe wirtschaftliche Kraft (Kleinst-/Einzelfirma, knappe Mittel).

Die Zahlungskräftigkeit lässt sich **nicht** aus der URL allein ableiten — sie muss pro Kunde aus **öffentlichen Quellen zusammengesucht und abgeschätzt** werden (z.B. Handelsregister/Zefix für Rechtsform, Web/Verzeichnisse für Grösse/Standorte/Branche). Schätzungen sind erlaubt, müssen aber als Schätzung nachvollziehbar sein.

## 4. Akzeptanzkriterien (bindend)

- **AC1 — Vollständigkeit:** Das Tool verarbeitet die **ganze Liste**, nicht Stichproben; auch mehrere hundert Zeilen, ohne manuelles Eingreifen pro Zeile.
- **AC2 — Output-Form:** Ausgabe = alle Original-Spalten unverändert + genau die zwei Score-Spalten (1–5, ganzzahlig). Keine leeren Scores.
- **AC3 — Score-Richtung:** Scores folgen exakt den Definitionen in Abschnitt 3 (höher = mehr Bedarf bzw. mehr Kaufkraft).
- **AC4 — Robustheit:** Ungültige/fehlende URL, nicht erreichbare Seite, Timeout, geparkte Domain, Social-Media-only → **kein Absturz**; sinnvoller Score (bei «keine Website» = Bedarf hoch) + Vermerk.
- **AC5 — Zahlungskräftigkeit aus öffentlichen Quellen:** Score 2 wird pro Kunde recherchiert/geschätzt; die genutzte Quelle bzw. die Annahme ist nachvollziehbar (Log oder Begründungsspalte). Keine erfundenen Fakten — fehlt die Datenlage, konservativ schätzen und kennzeichnen.
- **AC6 — Nachvollziehbarkeit:** Zu jedem Score ist erkennbar, welche Signale ihn getrieben haben (mind. in einem Lauf-Log).
- **AC7 — Wiederholbar & resümierbar:** Erneuter Lauf möglich; Zwischenergebnisse gecacht, sodass ein Abbruch nicht die ganze Arbeit verwirft.
- **AC8 — Limits:** Externe APIs mit Batching/Retry/Backoff nutzen, damit Rate-Limits nicht zum Abbruch führen.
- **AC9 — Bedienung:** Ein Einstiegspunkt/Befehl: Eingabedatei rein → Ausgabedatei raus. README erklärt Setup (inkl. API-Keys via `.env`) und Aufruf in <5 Minuten.
- **AC10 — Verifikation:** Gegen `data/sample_input.xlsx` lauffähig; Edge-Cases der Sample-Datei (leere URL, kaputte URL, grosse vs. kleine Firma) werden plausibel bewertet. Lege kurz dar, warum die Beispiel-Scores sinnvoll sind.
- **AC11 — Website-Bedarf aus sechs Dimensionen:** Score 1 wird gemäss `docs/scoring_website_bedarf.md` aus den sechs Dimensionen abgeleitet (keine Bauchnote). Je Kunde ist nachvollziehbar, welche Dimensionen den Score getrieben haben (Log oder Begründungsspalte). Mindestens die Dimensionen 1–4 müssen real gemessen werden (5/6 mindestens heuristisch).

## 5. Arbeitsweise

- **GSD — Getting Stuff Done, pragmatisch.** Zuerst die **kleinste lauffähige End-to-End-Version** (wenige Zeilen, beide Scores, Excel rein/raus), dann iterativ Qualität und Robustheit. Früh etwas Lauffähiges haben, nicht erst perfekt planen.
- **Du suchst den Weg.** Externe Dienste sind erlaubt, soweit nötig (PageSpeed/Lighthouse-API, LLM-API, Zefix/öffentliche Firmendaten, Web-Scraping). Das Resultat zählt. Wähle das, was die Akzeptanzkriterien am robustesten erfüllt.
- **Transparenz vor Eleganz.** Lieber ein nachvollziehbarer, einfacher Score-Mechanismus als eine Blackbox.

## 6. Nicht-Ziele (Scope-Schutz)

- Kein Dashboard, kein Dauerbetrieb, keine Salesforce-Integration, kein Web-Frontend. Das hier ist ein **lauffähiges Skript/CLI**: eine Excel rein, eine Excel raus.
- Keine Veröffentlichung von Personen-/Firmendaten; lokal arbeiten. `.env` und Ausgaben nicht committen.

## 7. Definition of Done

Ein Lauf über `data/sample_input.xlsx` erzeugt eine Ausgabe-Excel mit allen Original-Spalten plus den zwei Score-Spalten, alle Zeilen bewertet (inkl. Edge-Cases), die README erklärt Setup und Aufruf, und die Akzeptanzkriterien AC1–AC10 sind erfüllt.
