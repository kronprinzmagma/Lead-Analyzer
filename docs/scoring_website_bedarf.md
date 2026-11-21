# Scoring-Referenz: Website-Bedarf (Score 1, 1–5)

Der Score «Website-Bedarf» misst, **wie dringend ein Kunde eine moderne, professionelle Website braucht**. Er wird aus sechs messbaren Dimensionen abgeleitet — nicht als Bauchnote. Jede Dimension ist aus den Versprechen eines modernen Website-Produkts abgeleitet: Was ein modernes Website-Produkt verspricht, ist genau das, was einer schwachen Website fehlt.

## Die sechs Dimensionen

| # | Dimension | Was gemessen wird (Lücke = Bedarf) | Produkt-Bezug | Signal / Werkzeug |
|---|---|---|---|---|
| 1 | **Existenz & Substanz** | Erreichbar (HTTP 200)? Geparkt/Platzhalter? Nur Social-Media statt Website? Keine Website = maximaler Bedarf | Profi-Auftritt überhaupt | HTTP-Status, HTML-Inhalt, Redirect-Ziel |
| 2 | **Technische Basis** | HTTPS/gültiges SSL? Eigene Domain oder Gratis-Subdomain (wixsite, jimdosite, …)? | «Eigene Domain, SSL-zertifiziert» | SSL-Cert, HTTP-Header, Domain-Muster |
| 3 | **Mobile & Performance** | Responsive (Viewport-Meta)? Core Web Vitals / Ladezeit | «Responsive Design», Qualitäts-Check | PageSpeed-Insights-API (Mobile): zuerst Felddaten echter Besucher (CrUX: LCP/INP/CLS, 75. Perzentil, Seite oder sonst Domain), ohne Felddaten die Labormessung (Lighthouse) |
| 4 | **Auffindbarkeit (SEO)** | Title/Meta-Description vorhanden+Länge, Canonical, `lang`, H1, Indexierbarkeit (`noindex` per Meta-Robots oder X-Robots-Tag); robots.txt/sitemap.xml werden derzeit nicht geprüft | «SEO – auf Google gefunden» | HTML-Parse + HTTP-Header |
| 5 | **KI-/Answer-Engine-Bereitschaft** | Strukturiertes Markup (Schema.org/JSON-LD, Microdata), Open-Graph-Tags | «Sichtbar auf KI-Suchmaschinen» | Markup-Detektion im HTML |
| 6 | **Inhalt, Aktualität & Conversion** | Kontaktformular, `tel:`/`mailto:`, Impressum; Copyright-Jahr als Aktualitäts-Proxy; veralteter Builder/Generator (`<meta name="generator">`) | Gratis-Aktualisierung, Profi-Inhalte, Module | HTML-Parse |

Dimension 3 nutzt mit `PAGESPEED_API_KEY` die PageSpeed-Insights-API, ohne Key die Viewport-Heuristik; 1, 2, 4, 5, 6 kommen aus HTTP-Abruf + HTML-Parse. Dimension 6 (Aktualität/Textqualität) dürfte zusätzlich einen LLM-/Screenshot-Layer nutzen — aber **nach** den deterministischen Checks, als Ergänzung, nicht als Ersatz. Umgesetzt ist das nicht: im Scoring-Pfad läuft kein LLM.

## Aggregation zum 1–5-Score

| Score | Bedeutung |
|---|---|
| **5** | Keine/defekte Website ODER schwere Mängel über mehrere Dimensionen (z.B. kein HTTPS + nicht mobil + schwache PageSpeed + keine SEO-Basics) |
| **4** | Mehrere klare Lücken über verschiedene Dimensionen |
| **3** | Funktioniert, aber spürbare Lücken in ein bis zwei Dimensionen (z.B. veraltet, kein Mobile-Optimum) |
| **2** | Weitgehend solide, nur kleine Schwächen |
| **1** | Modern, schnell, mobil, gut auffindbar — kaum Bedarf |

**Aggregations-Hinweis (Weg frei wählbar):** Pro Dimension einen Teil-Befund (z.B. ok / Lücke / schwere Lücke) bilden, dann zum Gesamt-Score verdichten. Die genaue Gewichtung/Formel wählt die Implementierung — Hauptsache, der Score ist (a) aus den Dimensionen abgeleitet und (b) je Kunde nachvollziehbar (welche Dimensionen trieben den Score). «Keine erreichbare Website» überschreibt immer auf 5.

## Edge-Cases

- **Keine Website (leere URL):** Score 5, Vermerk «keine Website».
- **Defekte/nicht erreichbare URL:** Score 5, Vermerk «nicht erreichbar» (vor Endurteil kurz prüfen, ob nur Schema/`www` fehlt).
- **Nur Social-Media (Facebook/Instagram):** hoher Bedarf, eigener Vermerk «Social-only».
- **Geparkte Domain/Platzhalter:** wie «keine Website».
- **Abruf durch Schutzfilter blockiert** (HTTP 403/406/429 oder Challenge-Seite, z. B. «Just a moment…»): keine Note, Vermerk «nicht bewertbar»; Zeile am Schluss der Sortierung (Entscheid Nils 2026-11-19).
- **JavaScript-Hülle** (Single-Page-App, ausgeliefertes HTML ohne Inhalt): nicht «dünn»; Dim 5/6 werden aus der Hülle nicht beurteilt, Dim 2–4 (Technik, viewport, Kopfdaten) schon (Entscheid 2026-11-19).
- **Nur strukturiertes Markup fehlt** (Dim 5 einzige Lücke): höchstens Bedarf 2 (Entscheid 2026-11-19).
