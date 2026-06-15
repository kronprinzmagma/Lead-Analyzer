# Phase 9 Research — myWEBSITE Sales Arguments Sheet

**Confidence:** HIGH (product data fetched from localsearch.ch; deficit source already exists in code)
**Researched:** 2026-06-15

## Summary

Add a **second worksheet** to the output `.xlsx` that reframes each company's measured
**deficits** (the non-ok dimension verdicts already computed for the Website-Bedarf score)
into positive, sales-ready **myWEBSITE arguments**: customer name, its deficits, and the
myWEBSITE features that fix them with the concrete benefit. One row per company, same sorted
order as the main "Leads" sheet. Fully offline/deterministic — no LLM, no network, no
invented features. The deficit data already lives on `RowResult.verdicts`; this phase is a
**presentation layer**, not a new analysis.

## Phase Requirements

- **DIFF-04** (activated): second output sheet with myWEBSITE arguments per company.
- **NACH-01**: the arguments are traceable to the same dimension verdicts that drove the Bedarf score.

## Deficit source (already in code — no new analysis)

`RowResult.verdicts` is a `list[DimensionVerdict]` (see `lead_analyzer/models.py`). Each verdict:
- `dim`: 1..6
- `level`: `"ok"` | `"gap"` | `"severe"`
- `reason`: human-readable German note
- `dead`: True when "no/broken website" overrides Bedarf to 5

A **deficit** = a verdict with `level != "ok"` OR `dead == True`. This is the SAME driver set
`reasons.build()` already lists (see `lead_analyzer/reasons.py`: `drivers = [v for v in verdicts if v.level != "ok" or v.dead]`). Reuse that exact predicate so the argument sheet and the
Begründung column never disagree.

### CRITICAL edge case — empty verdicts on non-normal paths

On the **empty-URL path** and the **exception path**, `analyze_row` returns a `RowResult` with
`verdicts=[]` (no DimensionVerdict objects) but `bedarf=5` and a reason starting with
`"keine Website"` / `"Fehler:"` (see `lead_analyzer/pipeline.py:63-72` and `:101-113`).
So the argument builder MUST NOT rely solely on `verdicts`:
- If `verdicts` is non-empty → derive deficits from the non-ok/dead verdicts (normal path).
- If `verdicts` is empty AND `bedarf == 5` → treat as the **Dimension 1 "no reachable website"**
  deficit (map to the dim-1 argument). This covers Kiosk (empty URL) and Nähatelier (broken URL).

## myWEBSITE product (VERIFIED — fetched from localsearch.ch/de/unsere-kmu-loesungen/mywebsite/)

Feature set (used only as the right-hand side of the mapping; we do not list pricing in the sheet):
- **Domain & Security**: own `.ch` domain (customer-owned) + SSL certificate included.
- **Responsive design**: auto-adapts to PC/smartphone/tablet.
- **SEO**: expert-written content, optimised for Google; "listed on Google when customers search
  for your offering"; explicit **AI search-engine visibility** improvements.
- **Content**: professional copywriting/proofreading; self-editing via Admin Center; tiered updates.
- **Modules (M/L)**: Blog, Chat, E-Shop, Event/booking calendar, marketing tools; premium:
  membership area, site search, social feeds.
- **Admin Center**: dashboard + real-time visitor statistics.
- **Support**: on-site consultation, package guidance, account management.
- **Speed to market**: live in ~14 days ("Ihre Webseite in 14 Tagen live").
- Packages S/M/L (CHF 790 / 2'490 / 5'090+ setup) — context only, NOT shown per row.

## THE MAPPING (deterministic table — the core of this phase)

One entry per dimension. The builder emits, for each deficit dimension a company has, the
`feature` + `benefit` text. Keep this as a module-level constant (e.g. `mywebsite.py:_MAPPING`)
so it is testable and editable in one place.

| dim | Defizit (label) | myWEBSITE-Funktion | Konkreter Nutzen (Gewinn-Framing) |
|-----|-----------------|--------------------|-----------------------------------|
| 1 | Keine/defekte Website oder nur Social Media | Komplette professionelle Website in 14 Tagen live, inkl. eigener `.ch`-Domain | Überhaupt seriös online & auf Google auffindbar — statt nur Social-Profil oder gar nichts |
| 2 | Kein HTTPS/SSL oder nur Gratis-Subdomain | SSL-Zertifikat inklusive + eigene `.ch`-Domain | Kein „Nicht sicher"-Warnhinweis im Browser; eigene Adresse statt wixsite.com = Vertrauen & Seriosität |
| 3 | Nicht für Smartphones optimiert / langsam | Responsive Design (passt sich automatisch an Handy/Tablet/PC an) | Erreicht die Mehrheit der Besucher am Handy → weniger Absprünge, mehr Anfragen |
| 4 | Schlecht auf Google auffindbar (Title/Meta/Indexierung) | Profi-SEO + von Experten verfasste Inhalte; gelistet, wenn nach Ihrem Angebot gesucht wird | Wird organisch gefunden → qualifizierte Anfragen ohne Werbebudget |
| 5 | Nicht KI-/Answer-Engine-bereit (kein strukturiertes Markup) | Optimierung für KI-Suchmaschinen + strukturierte, gepflegte Inhalte | Auch in KI-Suchen (ChatGPT, Google AI) sichtbar → zukunftssicher auffindbar |
| 6 | Kaum Kontaktmöglichkeiten / veraltete Inhalte | Kontakt- & Chat-Modul, Admin-Center, regelmässige Updates, optional E-Shop/Termin-Kalender | Besucher werden zu Anfragen & Kunden; stets aktuelle Inhalte → mehr Abschlüsse |

**No-deficit case** (modern site, all dimensions ok, Bedarf 1): emit a single honest note —
`"Keine akuten Defizite — moderne Website über alle Dimensionen. Ansatz: Stärken sichern (Wartung/Service-Boost) bzw. ausbauen (E-Shop/Termin-Kalender)."` — never invent a deficit.

## Output structure (DECIDED: one row per company)

Second sheet title: **"myWEBSITE-Argumente"**. Columns:

| Kundenname | Defizite | myWEBSITE-Funktionen & Nutzen |
|------------|----------|-------------------------------|

- **Kundenname**: from the `Kundenname` cell if present (mirror `payment.py:151`); else fall back
  to the detected URL value, else `"Zeile {index+1}"`. (Planner: consider a tolerant name-column
  detection like `detect_url_column`, but the sample uses literal "Kundenname" — keep it simple.)
- **Defizite**: bullet list (newline-separated in the cell) of the company's deficit labels (col 2 of the mapping).
- **myWEBSITE-Funktionen & Nutzen**: bullet list, each line `{Funktion} → {Nutzen}` (cols 3+4 of the mapping).
- Rows in the SAME sorted order as the "Leads" sheet (reuse the already-sorted `ordered` pairs).
- Multi-line cells: set `wrap_text=True` on the two list columns for readability (openpyxl
  `Alignment(wrap_text=True, vertical="top")`).

## Wiring (file-level anchors)

- `lead_analyzer/table_io.py`:
  - `write_output(path, headers, ordered, reason_column, write_csv)` currently builds ONE sheet
    in `_write_xlsx` (`wb.active`, title "Leads"). Add a second sheet via `wb.create_sheet("myWEBSITE-Argumente")`
    and append the argument rows from the same `ordered` pairs. The "Leads" sheet bytes/columns
    stay UNCHANGED (success criterion 4).
  - CSV has no sheets: when CSV output is requested, write a companion `*_argumente.csv` next to
    the main CSV (same stem + `_argumente.csv`), OR document that arguments are xlsx-only. Planner picks one; companion CSV is preferred for parity.
- `lead_analyzer/mywebsite.py` (NEW): holds `_MAPPING`, the no-deficit note, and
  `build_arguments(record, result, name_col=None) -> tuple[str, str, str]` returning
  `(kundenname, defizite_text, funktionen_text)`. Pure function, no I/O — fully unit-testable.
  Mirror the purity of `reasons.py`.
- No change to `pipeline.py` analysis is required — `RowResult.verdicts` already carries the data.
  `pipeline.run()` already passes `ordered` to `table_io.write_output`; the second sheet is built there.

## Validation Architecture

nyquist_validation enabled. Offline, deterministic — easy to test.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Quick run | `.venv/bin/python -m pytest tests/test_mywebsite.py tests/test_phase1_io.py -x -q` |
| Full suite | `.venv/bin/python -m pytest -x -q` |

### Req → Test Map
| Req | Behavior | Test |
|-----|----------|------|
| DIFF-04 | each dimension's gap/severe verdict → its mapped Funktion+Nutzen | `tests/test_mywebsite.py::test_each_dimension_maps` |
| DIFF-04 | empty verdicts + bedarf 5 → dim-1 "no website" argument | `tests/test_mywebsite.py::test_empty_verdicts_no_website` |
| DIFF-04 | all-ok (Bedarf 1) → "keine akuten Defizite" note, no invented deficit | `tests/test_mywebsite.py::test_no_deficit_note` |
| DIFF-04 | Kundenname fallback (no name column → URL/row index) | `tests/test_mywebsite.py::test_name_fallback` |
| DIFF-04 | output xlsx has 2 sheets; sheet 2 = "myWEBSITE-Argumente" with 3 headers + one row per company in sorted order | `tests/test_phase1_io.py::test_second_sheet_structure` (or new test_table_io) |
| DIFF-04 | "Leads" sheet unchanged (all original cols + 2 scores + order) | existing test_phase1_io assertions must still pass |
| NACH-01 | deficits in the sheet == non-ok/dead verdict drivers (same as reasons.build) | `tests/test_mywebsite.py::test_deficits_match_reason_drivers` |

### Wave 0
- [ ] `tests/test_mywebsite.py` — mapping + builder unit tests (RED first)
- [ ] second-sheet structure test in test_phase1_io.py / new test_table_io.py

## Security Domain
Low. No new inputs, no network, no credentials. Only risk: a malformed/missing `Kundenname`
cell → must not raise (use `str(... or "")` like payment.py). The argument text is static
constants, not user-echoed. Keep the builder exception-free so a weird row can't break output.

## Assumptions Log
- Sheet name "myWEBSITE-Argumente" (German, matches the audience). Adjustable.
- One row per company (user decision). Deficits/arguments as newline bullet lists in cells.
- Pricing/packages intentionally NOT shown per row (keeps the sheet about fit, not quoting).

## Open Questions (non-blocking)
- CSV parity: companion `*_argumente.csv` vs xlsx-only. Planner decides; companion preferred.
- Whether to also show the Bedarf/Zahl score on the argument sheet for context (probably not — keep it focused per the user's spec: name + deficits + features/benefit).

## RESEARCH COMPLETE
