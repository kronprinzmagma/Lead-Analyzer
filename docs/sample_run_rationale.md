# Sample-Run-Begründung (AC10)

Dieses Dokument belegt gemäss **AC10**, dass die Beispiel-Scores über `data/sample_input.xlsx`
plausibel sind. Es dokumentiert den reproduzierbaren Lauf, die Score-Verteilung und begründet
die wichtigsten Fälle — inklusive der zwei Edge-Cases und des Gross-gegen-klein-Kontrasts.

## Lauf

```
python run.py data/sample_input.xlsx -o output/sample_rationale.xlsx
```

- **42 Zeilen verarbeitet** (URL-Spalte automatisch erkannt: `Website`).
- Der Lauf läuft **offline / ohne API-Key**: ohne gesetzten `PAGESPEED_API_KEY` ist die
  PageSpeed-Insights-Abfrage (PSI) ausgeschaltet. Dimension 3 (Mobile & Performance) fällt
  dann auf die **Viewport-Heuristik** zurück (`viewport`-Meta-Tag vorhanden = mobil-tauglich),
  statt Core Web Vitals zu messen. Alle anderen Dimensionen (1, 2, 4, 5, 6) werden vollständig
  aus HTTP-Abruf + HTML-Parse gemessen.
- Die Ausgabedatei (`output/`) ist gitignoriert und wird nicht committet.

## Verteilung

Über alle 42 Zeilen:

| Score | Website-Bedarf (1–5) | Zahlungskräftigkeit (1–5) |
|-------|---------------------:|--------------------------:|
| 1     | 3                    | 3                         |
| 2     | 12                   | 9                         |
| 3     | 15                   | 10                        |
| 4     | 10                   | 7                         |
| 5     | 2                    | 13                        |
| **Σ** | **42**               | **42**                    |

Die Verteilung ist plausibel: Der **Website-Bedarf** häuft sich im Mittelfeld (Score 2–3 =
27 von 42), wenige Seiten sind rundum modern (Bedarf 1 = 3) und nur 2 Fälle sind die harten
Edge-Cases (Bedarf 5 = keine/defekte Website). Die **Zahlungskräftigkeit** ist breiter
gestreut und kopflastiger (Score 5 = 13), weil das Sample bewusst viele AG-/GmbH-/Treuhand-
und Immobilien-Firmen enthält, deren Rechtsform und Branche eine hohe Kaufkraft signalisieren.

## Edge-Cases

Beide Sonderfälle landen korrekt bei **Bedarf 5** — und vor allem: **kein Absturz** (AC4).

### Kiosk am Lindenplatz — leere URL → Bedarf 5

- **URL:** _(leer)_ · **Bedarf 5**, **Zahlungskräftigkeit 1**
- Begründung-Spalte: `keine Website | Zahl (Schätzung): Branchen-Tier (Annahme): Detailhandel → tief`
- Greift die Regel **«Keine erreichbare Website überschreibt immer auf 5»** aus
  `docs/scoring_website_bedarf.md`. Ein Kunde ohne Website hat den maximalen Website-Bedarf.
- Die Zahlungskräftigkeit 1 ist sachgerecht: ein Detailhandels-Kiosk ist eine Kleinstfirma
  mit geringer Kaufkraft. Score und Bedarf passen — aber ein hoher Bedarf bei tiefer Kaufkraft
  macht den Kiosk **nicht** zum Top-Lead.

### Nähatelier Sutter — kaputte `htp://`-URL → Bedarf 5

- **URL:** `htp://naehatelier-sutter` (Tippfehler im Schema, kein gültiger Host)
  · **Bedarf 5**, **Zahlungskräftigkeit 2**
- Begründung-Spalte: `Dim1 schwere Lücke (nicht erreichbar); Dim2 schwere Lücke (ungültiges
  SSL-Zertifikat); Dim3 Lücke (kein viewport-meta …) → Bedarf 5`
- **Robustheit (AC4):** Eine kaputte URL führt nicht zum Crash — das Tool verbucht «nicht
  erreichbar» + «ungültiges SSL» als schwere Lücken und überschreibt sauber auf Bedarf 5.
- Zahlungskräftigkeit 2: ein kleines Handwerks-/Näh-Atelier liegt im unteren Mittelfeld.

## Gross vs. klein (Zahlungskräftigkeit)

Die Zahlungskräftigkeit lässt sich nicht aus der URL ableiten — sie wird pro Kunde aus
öffentlichen Signalen (Rechtsform im Firmennamen, Branchen-Tier, Team-/Über-uns-Hinweise)
**geschätzt und als Schätzung gekennzeichnet** (AC5). Das zeigt der Kontrast deutlich:

**Hohe Kaufkraft — die idealen Leads (oben in der Sortierung):**

| Kunde | Bedarf | Zahl | Treiber (aus Begründung) |
|-------|:------:|:----:|--------------------------|
| KMU Treuhandexperte GmbH | 4 | 5 | `Rechtsform GmbH aus Firmenname angenommen; Branchen-Tier: Treuhand → hoch; Team-/Über-uns-Seite` |
| Lippuner Immobilien & Verwaltungen AG | 4 | 5 | `Rechtsform AG aus Firmenname angenommen; Branchen-Tier: Immobilien → hoch; Team-/Über-uns-Seite` |
| Oerlikon Zahnarzt | 4 | 4 | `Branchen-Tier: Zahnarzt → hoch; Team-/Über-uns-Seite` |

Diese Firmen haben echtes **Verbesserungspotenzial** (Bedarf 4: dünner Inhalt, SEO-/Markup-
Lücken) **und** hohe Kaufkraft (GmbH/AG + kaufkräftige Branche) — also genau die besten
Verkaufsziele.

**Tiefe Kaufkraft — schlechter Lead trotz funktionierender Seite:**

| Kunde | Bedarf | Zahl | Treiber |
|-------|:------:|:----:|---------|
| Coiffure Heidi | 1 | 1 | `alle Dimensionen ok → Bedarf 1`; `Branchen-Tier: Coiffeur → tief` |

Ein Ein-Personen-Coiffeursalon mit moderner Website: korrekt **Bedarf 1** (kein Handlungsbedarf)
und **Zahlungskräftigkeit 1** — kein lohnendes Ziel.

**Cluster «kein Bedarf»:** `ONE! Treuhand` erreicht **Bedarf 1** (`alle Dimensionen ok`) bei
**Zahlungskräftigkeit 4** — eine gute, moderne Seite ergibt korrekt einen tiefen Bedarf, auch
bei kaufkräftiger Firma. Hohe Kaufkraft allein macht keinen Lead, solange die Website schon gut ist.

**Sortierung:** Die Standard-Sortierung (`Website-Bedarf` absteigend, dann
`Zahlungskräftigkeit` absteigend, CLAUDE.md §3) stellt damit automatisch die idealen Leads
mit **hohem Bedarf UND hoher Kaufkraft** (z.B. KMU Treuhandexperte GmbH B4/Z5) nach oben.

## So liest man die Begründung-Spalte

Jede Zeile trägt eine `Begründung`-Spalte mit zwei durch `|` getrennten Teilen (AC6):

1. **Website-Bedarf:** pro Dimension der Befund (`Dim1 … Dim6`, jeweils _ok_ / _Lücke_ /
   _schwere Lücke_ mit konkretem Signal), gefolgt von `→ Bedarf N`. Bei leerer URL nur `keine Website`.
2. **Zahlungskräftigkeit:** mit Präfix `Zahl (Schätzung):` — Rechtsform-Annahme (Quelle:
   Firmenname), Branchen-Tier und weitere Signale. Das Präfix macht transparent, dass es sich
   um eine **dokumentierte Schätzung** handelt, keine erfundene Tatsache (AC5).

Hinweis: In diesem Lauf wurde Dimension 3 über die **Viewport-Heuristik** bewertet (kein
PSI-Key gesetzt). Mit gesetztem `PAGESPEED_API_KEY` würden hier zusätzlich reale Core Web
Vitals einfliessen; die Bedarf-Richtung bleibt gleich.
