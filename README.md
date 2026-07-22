# FIT-Connect AI-Mapper

Baut aus den Feldern einer Formular-Maske automatisch:

1. ein FIM-konformes **Referenzschema** (XDatenfelder-2.0-XML → XSD), unter Wiederverwendung
   bestehender, fachlich freigegebener FIM-Datenfelder wo möglich — als selbst hostbare Datei
   (GitHub, eigener Formularserver), damit sie in FIT-Connect per URI referenziert werden kann.
2. ein **FORMCYCLE-Plugin-Template** (JSON, direkt in den FIT-Connect-Editor kopierbar) zur
   Gruppen-/Objektinitialisierung - inklusive Bindung jedes FIM-Datenfelds an den technischen
   Namen des Webformularfelds über FORMCYCLE-Platzhalter-Syntax (`[%$variable%]`).

Hintergrund: siehe `../Ausgangslage.docx`. Für viele Verwaltungsleistungen (LeiKa-Nummern) gibt
es noch kein FIM-Referenzschema. Dieses Tool schließt die Lücke, statt das Schema manuell
zusammenzubauen.

## Eigenständig nutzbar – kein Claude/Claude-Code nötig

Das Tool läuft komplett unabhängig, per Web-UI, CLI oder Docker. Weder Claude Code noch diese
Session werden zur Laufzeit gebraucht:

- **Web-UI**: Formular hochladen → ZIP mit allen vier Ausgabedateien herunterladen.
- **CLI**: `python -m ai_mapper.cli map ...` – ideal für Skripte/Automatisierung.
- **Matching ohne LLM**: `ANTHROPIC_API_KEY` ist optional. Ohne Key läuft ein regelbasierter
  Fallback (String-Ähnlichkeit + Datentyp-Prüfung). Mit Key übernimmt Claude das semantische
  Matching (bessere Qualität bei unterschiedlichem Wortlaut, z. B. "Nachname" ↔ "Familienname").
  Der Kunde kann später seinen eigenen Key hinterlegen, ganz ohne diese Konversation.

## Funktionsweise

Für jedes Formularfeld wird live die öffentliche [FIM-Portal-API](https://fimportal.de) nach
passenden bestehenden Datenfeldern durchsucht. Ein Matching-Schritt entscheidet je Feld:

- **REUSE** – ein bestehendes, fachlich freigegebenes FIM-Datenfeld wird 1:1 übernommen
  (Herkunft bleibt nachvollziehbar: `namespace/fim_id/fim_version`).
- **NEU** – es existiert keine passende Vorlage, es wird ein neues Datenfeld angelegt (eigener,
  nicht mit der Bundesredaktion kollidierender Nummernkreis `9xxxxxxx`).

Ein Datenfeld wird nur wiederverwendet, wenn zusätzlich der FIM-Datentyp zum Formularfeldtyp
passt (verhindert Fehltreffer wie "Geburtsdatum" ↔ "Geburtsname" – ähnlicher Wortlaut, aber
komplett andere Bedeutung und Datentyp).

Das komponierte Schema wird über die offiziellen FIM-Portal-Konverter in eine gültige XSD
(`POST /tools/xdf2-xsd-converter`) **und** ein JSON Schema (`POST /tools/xdf2-json-schema-converter`)
umgewandelt — kein selbstgebauter, fehleranfälliger Konverter nötig. Beide werden gebraucht: die
XSD als "URI-Schema" für den klassischen FIT-Connect-XML-Weg, das JSON Schema für FORMCYCLEs
Nachrichtentyp "JSON Struktur aus Editor" (siehe unten).

### BOB-Bausteine über die LeiKa-Nummer (`bob_context.py`)

Wird eine LeiKa-Nummer mitgegeben, sucht der Mapper zusätzlich die **fachlich passenden
BOB-Bausteine** ("Baukasten optimierter Bausteinelemente") – z. B. die Sozialamt- oder
Gesundheitsamt-spezifischen Standardfelder statt generischer Treffer. FIM pflegt dafür keine
offizielle LeiKa→BOB-Zuordnungstabelle (recherchiert, FIM verweist auf Einzelfallprüfung durch
Modellierer). Stattdessen wird empirisch vorgegangen und live verifiziert:

1. LeiKa-Nummer → Leistungsbeschreibung (Rechtsgrundlage, OZG-Themenfeld) über
   `/api/v1/leistung-steckbriefe`.
2. Mit der Rechtsgrundlage nach bereits freigegebenen, ähnlichen FIM-Referenzschemata suchen
   (`/api/v1/schemas`).
3. Aus diesen Schemata die tatsächlich verwendeten BOB-Bausteine (Nummernkreis `60000`)
   extrahieren und als priorisierte Kandidaten fürs Matching nutzen.

**Verifiziertes Beispiel:** LeiKa `99003002022000` ("Belehrung nach dem Infektionsschutzgesetz
Bescheinigung", Rechtsgrundlage "§ 43 Absatz 1 IfSG") findet als Top-Treffer exakt das reale
Referenzschema [S00000253](https://fimportal.de/schemas/S00000253/1.0/structure?resource=schema)
und dessen ~20 BOB-Bausteine (Anschrift, Kommunikation, Namensfelder etc.) – siehe
`tests/test_bob_context.py`. Dieser Schritt funktioniert komplett ohne LLM.

Das Matching selbst läuft mit Claude (Anthropic API), wenn `ANTHROPIC_API_KEY` gesetzt ist. Ohne
Key nutzt es einen regelbasierten Fallback (String-Ähnlichkeit + Datentyp-Prüfung) – die
Pipeline bleibt so auch ohne LLM-Zugang lauffähig, allerdings mit einfacherer Matching-Qualität
bei unterschiedlichem Wortlaut.

### FORMCYCLE-Editor-Template (`formcycle_export.py`)

Verifiziert anhand eines echten Editor-Screenshots des FIT-Connect-Plugins (vom Kunden
bereitgestellt, 2026-07-22). Der Editor hat u. a. diese Felder:

| Editor-Feld | Beispiel aus dem Screenshot |
|---|---|
| Empfänger-/Zustellpunkt-UUID | `1436f7a6-e4cc-4100-8ecd-a198e453f104` (aus SSP-Registrierung) |
| Service Identifier (LeiKa-ID) | `urn:de:xima:formcycle:leistung:00000000000003` |
| Service Bezeichnung | `Usergroup Workshop FIT-Connect` |
| Art der Nachricht | `JSON Struktur aus Editor` |
| Nachricht im JSON-Format | `{"someString":"[%$PROJECT_TITLE%]"}` |
| Schema-URI | (öffentliche URL des Schemas) |

Zwei wichtige Erkenntnisse daraus:

1. **FORMCYCLE-Platzhalter-Syntax ist `[%$NAME%]`**, nicht `%NAME%`.
2. Bei "JSON Struktur aus Editor" ist die Nachricht **direkt die Fachdaten-Nutzlast** – keine
   Mapping-Metadatenstruktur. Ihre Property-Namen entsprechen exakt den Keys des über
   `/tools/xdf2-json-schema-converter` erzeugten JSON Schemas: `{FIM-ID}V{Version}`
   (z. B. `F60000228V2.0`), verschachtelt pro Datenfeldgruppe (z. B. `G00002115V1.0`).

`formcycle-plugin-mapping.json` bildet das direkt ab:

```json
{
  "editorFelder": {
    "empfaengerZustellpunktUuid": "<im FIT-Connect-SSP nachschlagen>",
    "serviceIdentifier": "urn:de:linde-consulting:ai-mapper:leistung:99003002022000",
    "serviceBezeichnung": "Meldeformular Infektionsschutz Gesundheitsamt",
    "artDerNachricht": "JSON Struktur aus Editor",
    "schemaUri": "https://.../schema.jsonschema.json"
  },
  "nachrichtImJsonFormat": {
    "G00002115V1.0": { "F60000228V2.0": "[%$tf1_st_Vorname%]" },
    "F92331743V1.0": "[%$tf1_st_Nachname%]"
  }
}
```

`nachrichtImJsonFormat` ist 1:1 in das Editor-Feld "Nachricht im JSON-Format" kopierbar. Die
Gruppenzuordnung (`G00002115V1.0`) kommt aus dem BOB-Domain-Kontext (siehe oben); Felder ohne
bekannte Ursprungsgruppe (neue Felder oder generische Treffer ohne Gruppen-Info) liegen auf der
obersten Ebene. Der `serviceIdentifier` nutzt eine an das Screenshot-Beispiel angelehnte URN mit
der eigenen LeiKa-Nummer – die genaue URN-Konvention ist vendor-/instanzabhängig (das
Screenshot-Beispiel nutzt eine laufende interne Nummer, keine offizielle LeiKa) und muss ggf. an
die tatsächliche SSP-Konvention der Behörde angepasst werden.

**Wichtige Einschränkung:** Ohne 1:1-Abgleich an einem konkret konfigurierten
FIT-Connect-Zustellpunkt bleibt das ein **Template**, klar als Annahme gekennzeichnet
(`_hinweis`-Feld) – die übrigen Editor-Felder (Zustellpunkt-UUID, Vorgangs-ID) sind
umgebungsspezifisch und müssen manuell ergänzt werden.

## Lokal starten

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# optional: ANTHROPIC_API_KEY in .env eintragen

export PYTHONPATH=src

# CLI - vollständige Formular-JSON
python -m ai_mapper.cli map --input examples/beispiel-formular.json --output out/

# CLI - CSV/XLSX-Feldtabelle (Titel + LeiKa-Nummer als Parameter)
python -m ai_mapper.cli map --input examples/formular-vorlage.csv \
  --titel "Meldeformular Infektionsschutz Gesundheitsamt" \
  --leika-nummer 99003002022000 \
  --output out/

# oder Web-UI
uvicorn ai_mapper.api:app --reload
# -> http://localhost:8000 (Formular-Upload, Vorlage-Download unter /vorlage)
```

## Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src pytest
```

`tests/test_fim_client.py` und `tests/test_pipeline_end_to_end.py` sind Live-Smoke-Tests gegen
die echte FIM-Portal-API (Internetzugriff nötig).

## Selbst-Hosting (Docker)

```bash
cp .env.example .env   # ANTHROPIC_API_KEY eintragen
docker compose up --build
```

Läuft dann auf Port 8000 – geeignet für den Betrieb auf einem eigenen Application Server beim
Kunden. Nur `.env` ist Kunden-spezifisch zu konfigurieren.

## Formular-Input-Format

Drei gleichwertige Wege, alle erzeugen intern dasselbe `FormularInput`:

### Echter FORMCYCLE-Export ("Formular exportieren" im Editor)

Wird automatisch erkannt (Top-Level-Key `items`) und über `formcycle_import.py` geparst.
Layout-/Deko-Elemente (Header, Seiten, Footer, Buttons, Bilder, Captcha, ...) werden
übersprungen, nur echte Eingabefelder übernommen. Der Formular-Titel wird aus dem Export
übernommen, falls nicht separat angegeben. Verifiziert mit einem echten Export
(`examples/webform-Neues Formular.json`, siehe `tests/test_formcycle_import.py`).

Unterstützte FORMCYCLE-Feldtypen: `XTextField`/`XTextfieldAdvanced` (Text, ggf. per
`datatypeHint` verfeinert zu E-Mail/Telefon/Zahl/Betrag), `XTextArea` (mehrzeilig),
`XSelect`/`XDatalistAdvanced` (Auswahl), `XCheckbox`, `XUpload` (Datei), `XAppointment`
(Datum). Andere Feldtypen (Signatur, Formel, Bewertung, Karte, ...) werden aktuell
übersprungen.

### CSV/XLSX-Feldtabelle (für den Kunden gedacht, kein Formcycle-Rohexport nötig)

Formcycle bietet keinen dokumentierten Rohexport der Feld-Definitionen (Typ, Pflicht, Bezug) als
einfaches CSV – nur einen Submission-Datenexport (Spalten = Feld-Label, ohne Metadaten) und einen
komplexen internen Formular-Export (undokumentiert). Deshalb definiert `formular_import.py` einen
eigenen, einfachen Tabellen-Vertrag, den der Kunde manuell aus Formcycle ableiten oder direkt so
pflegen kann – siehe [`examples/formular-vorlage.csv`](examples/formular-vorlage.csv) (per Web-UI
auch unter `/vorlage` herunterladbar):

| Abschnitt | Feld-ID | Label | Typ | Pflichtfeld | Optionen | Hilfetext |
|---|---|---|---|---|---|---|
| Angaben zur betroffenen Person | nachname | Nachname | text | ja | | |

Nur **Label** und **Typ** sind zwingend; **Feld-ID** wird sonst aus dem Label abgeleitet. Titel
und LeiKa-Nummer werden separat übergeben (CLI-Flags bzw. Web-UI-Felder), da eine flache
Feldtabelle keinen natürlichen Platz für Dokument-Metadaten hat. Unterstützt `.csv` und `.xlsx`.

### Formular-JSON (Titel/LeiKa bereits enthalten)

```json
{
  "titel": "Meldeformular Infektionsschutz Gesundheitsamt",
  "leika_nummer": "99089009123000",
  "felder": [
    {
      "id": "nachname",
      "label": "Nachname",
      "typ": "text",
      "pflichtfeld": true,
      "abschnitt": "Angaben zur betroffenen Person"
    }
  ]
}
```

Unterstützte `typ`-Werte: `text`, `mehrzeilig`, `email`, `tel`, `zahl`, `ganzzahl`, `betrag`,
`datum`, `auswahl`, `checkbox`, `datei`.

## Output

- `schema.xdf.xml` – komponiertes XDatenfelder-2.0-Referenzschema
- `schema.xsd` – daraus generierte XSD ("URI-Schema" für FIT-Connect/SSP, klassischer XML-Weg)
- `schema.jsonschema.json` – daraus generiertes JSON Schema (für FORMCYCLEs "JSON Struktur aus Editor")
- `formcycle-plugin-mapping.json` – direkt in den FIT-Connect-Editor kopierbares Template
  (Gruppen + `[%$...%]`-Platzhalter-Bindung, siehe oben)
- `mapping-report.md` – Transparenz: welches Feld wiederverwendet/neu, mit Begründung

## Veröffentlichung des Schemas (manuell)

Damit die XSD per URI aus FIT-Connect/FORMCYCLE erreichbar ist, `schema.xsd` in ein
öffentliches GitHub-Repo (z. B. GitHub Pages) oder auf den eigenen Formularserver legen und die
resultierende URL in `formcycle-plugin-mapping.json` (`schemaUri`) sowie bei der
Zustellpunkt-Registrierung im SSP eintragen. Dieser Schritt ist bewusst nicht automatisiert.

## Bekannte Grenzen / nächste Schritte

- Datenfelder mit Codelisten (Auswahllisten) werden aktuell nicht mitkonvertiert – der
  XSD-Konverter benötigt dafür zusätzlich die referenzierten Codelisten-Dateien
  (`/api/v0/code-lists`). Für die bisher unterstützten Feldtypen ohne Codeliste ist das kein
  Thema.
- Feldtyp `auswahl` (Dropdown/Radio) wurde noch nicht Ende-zu-Ende gegen den XSD-Konverter
  getestet (aktuell als Freitext-`praezisierung` statt echter Codeliste abgebildet) – vor
  Nutzung mit einem echten Auswahlfeld verifizieren.
- Kein automatisches Publizieren nach GitHub (bewusst, siehe oben).
- FORMCYCLE-Template ungeprüft an einem konkreten Zustellpunkt (siehe Hinweis oben) – Struktur
  folgt einem echten Editor-Screenshot, aber ohne 1:1-Abgleich an einer produktiven Konfiguration.
  Zustellpunkt-UUID und Vorgangs-ID sind umgebungsspezifisch und bleiben Platzhalter.
- Matching ist feldweise, nicht gruppenweise: eine zusammengehörige BOB-Datenfeldgruppe (z. B.
  "Anschrift Inland" mit Straße/PLZ/Ort) wird aktuell als einzelne Felder erkannt, nicht als
  Gruppe im Ganzen übernommen. Für den FORMCYCLE-Export werden REUSE-Felder aber wieder korrekt
  nach ihrer Ursprungsgruppe verschachtelt (`nachrichtImJsonFormat`).
- Der regelbasierte Fallback (ohne `ANTHROPIC_API_KEY`) erkennt keine Synonyme
  ("Nachname" vs. "Familienname") – dafür ist der Claude-Pfad deutlich zuverlässiger.
- CSV/XLSX-Spaltenformat ist ein von uns definierter Vertrag, kein echter Formcycle-Rohexport
  (siehe oben) – bei Bedarf später an ein reales Formcycle-Exportformat anpassen.
