# Scoring-Referenz: Website-Bedarf (Score 1, 1–5)

Der Score «Website-Bedarf» misst, **wie dringend ein Kunde eine moderne Website (MyWEBSITE) braucht**. Er wird aus sechs messbaren Dimensionen abgeleitet — nicht als Bauchnote. Jede Dimension ist aus localsearchs eigenen MyWEBSITE-Versprechen abgeleitet: Was MyWEBSITE verspricht, ist genau das, was einer schwachen Website fehlt.

## Die sechs Dimensionen

| # | Dimension | Was gemessen wird (Lücke = Bedarf) | MyWEBSITE-Bezug | Signal / Werkzeug |
|---|---|---|---|---|
| 1 | **Existenz & Substanz** | Erreichbar (HTTP 200)? Geparkt/Platzhalter? Nur Social-Media statt Website? Keine Website = maximaler Bedarf | Profi-Auftritt überhaupt | HTTP-Status, HTML-Inhalt, Redirect-Ziel |
| 2 | **Technische Basis** | HTTPS/gültiges SSL? Eigene Domain oder Gratis-Subdomain (wixsite, jimdosite, …)? | «Eigene Domain, SSL-zertifiziert» | SSL-Cert, HTTP-Header, Domain-Muster |
| 3 | **Mobile & Performance** | Responsive (Viewport-Meta)? Core Web Vitals / Ladezeit | «Responsive Design», Qualitäts-Check | PageSpeed-Insights-API (Performance, Mobile) |
| 4 | **Auffindbarkeit (SEO)** | Title/Meta-Description vorhanden+Länge, Canonical, robots/sitemap, Überschriften, Indexierbarkeit | «SEO – auf Google gefunden» | Lighthouse-SEO + HTML-Parse |
| 5 | **KI-/Answer-Engine-Bereitschaft** | Strukturiertes Markup (Schema.org/JSON-LD), Open-Graph-Tags, klare Themenstruktur | «Sichtbar auf KI-Suchmaschinen» | Markup-Detektion im HTML |
| 6 | **Inhalt, Aktualität & Conversion** | Kontaktformular, `tel:`/`mailto:`, Impressum; Copyright-Jahr/Last-Modified als Aktualitäts-Proxy; veralteter Builder/Generator | Gratis-Aktualisierung, Profi-Inhalte, Module | HTML-Parse; optional LLM/Screenshot fürs Qualitative |

Dimensionen 3–4 liefert die PageSpeed-Insights-API in einem Call; 1, 2, 5, 6 kommen aus HTTP-Abruf + HTML-Parse. Dimension 6 (Aktualität/Textqualität) darf zusätzlich einen LLM-/Screenshot-Layer nutzen — aber **nach** den deterministischen Checks, als Ergänzung, nicht als Ersatz.

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
