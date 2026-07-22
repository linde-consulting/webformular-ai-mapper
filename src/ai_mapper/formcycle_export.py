"""Erzeugt die zweite Ausgabedatei: ein direkt in den echten FORMCYCLE-FIT-Connect-
Plugin-Editor kopierbares Template ("Eigenschaften" + "Nachricht im JSON-Format").

Verifiziert anhand eines echten Editor-Screenshots (vom Nutzer bereitgestellt,
2026-07-22) mit folgenden Feldern:

- Empfänger-/Zustellpunkt-UUID          (kommt aus der SSP-Registrierung - unbekannt)
- FIT-Connect Vorgangs-ID               (optional, laufzeitspezifisch - unbekannt)
- Service Identifier (LeiKa-ID)         Beispiel im Screenshot:
                                        "urn:de:xima:formcycle:leistung:00000000000003"
- Service Bezeichnung                   Freitext
- Art der Nachricht                     "JSON Struktur aus Editor" (neben XML-Modus)
- Nachricht im JSON-Format              Beispiel im Screenshot: {"someString":"[%$PROJECT_TITLE%]"}
                                        -> FORMCYCLE-Platzhalter-Syntax ist "[%$NAME%]",
                                        NICHT "%NAME%"!
- Schema-URI                            Öffentliche URL des Schemas

Bei "JSON Struktur aus Editor" ist die Nachricht direkt die Fachdaten-Nutzlast, keine
Mapping-Metadatenstruktur. Deren Feldnamen entsprechen exakt den Property-Namen des
über /tools/xdf2-json-schema-converter erzeugten JSON Schemas: "{FIM-ID}V{Version}"
(z. B. "F60000228V2.0"), verschachtelt pro Datenfeldgruppe (z. B. "G00002115V1.0").
Live verifiziert (siehe tests/test_formcycle_export.py).

Die "Service Identifier"-URN ist vendor-/instanzabhängig (das Beispiel nutzt eine
laufende interne Nummer, keine offizielle 14-stellige LeiKa-Nummer) - hier wird die
eigene LeiKa-Nummer in einer analogen URN-Struktur eingesetzt, muss aber ggf. an die
tatsächliche SSP-Konvention der Behörde angepasst werden.

WICHTIG: Nach wie vor ohne 1:1-Abgleich an einem echten, fertig konfigurierten
FORMCYCLE-Zustellpunkt - Struktur folgt dem bereitgestellten Screenshot, nicht einer
öffentlichen Spezifikation.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .models import Formularfeld, MatchErgebnis

ANNAHME_HINWEIS = (
    "ANNAHME / TEMPLATE, basierend auf einem echten Editor-Screenshot (2026-07-22), aber "
    "ohne 1:1-Abgleich an einem konkreten FORMCYCLE-Zustellpunkt. FORMCYCLE-Platzhalter-Syntax "
    "ist '[%$NAME%]'. JSON-Property-Namen entsprechen den Keys des über "
    "/tools/xdf2-json-schema-converter erzeugten JSON Schemas ('{FIM-ID}V{Version}')."
)


def _formcycle_platzhalter(technischer_name: str) -> str:
    return f"[%${technischer_name}%]"


def _property_key(fim_id: str, fim_version: str) -> str:
    return f"{fim_id}V{fim_version}"


def build_formcycle_template(
    schema_id: str,
    schema_version: str,
    titel: str,
    felder: List[Formularfeld],
    matches: List[MatchErgebnis],
    leika_nummer: Optional[str] = None,
    schema_uri: Optional[str] = None,
) -> str:
    technischer_name_je_feld = {f.id: (f.technischer_name or f.id) for f in felder}

    nachricht: Dict[str, object] = {}
    gruppen_objekte: Dict[str, Dict[str, object]] = {}

    for m in matches:
        platzhalter = _formcycle_platzhalter(technischer_name_je_feld.get(m.feld_id, m.feld_id))

        if m.status == "REUSE" and m.fim_kandidat:
            key = _property_key(m.fim_kandidat.fim_id, m.fim_kandidat.fim_version)
            gruppe_id = m.fim_kandidat.gruppe_id
            gruppe_version = m.fim_kandidat.gruppe_version
        else:
            key = _property_key(m.neue_id or m.feld_id, "1.0")
            gruppe_id = None
            gruppe_version = None

        if gruppe_id:
            gruppen_key = _property_key(gruppe_id, gruppe_version or "1.0")
            ziel = gruppen_objekte.setdefault(gruppen_key, {})
            ziel[key] = platzhalter
            nachricht[gruppen_key] = ziel
        else:
            nachricht[key] = platzhalter

    service_identifier = f"urn:de:linde-consulting:ai-mapper:leistung:{leika_nummer or schema_id.lower()}"

    ergebnis = {
        "_hinweis": ANNAHME_HINWEIS,
        "editorFelder": {
            "empfaengerZustellpunktUuid": "<im FIT-Connect-SSP nachschlagen>",
            "fitConnectVorgangsId": "",
            "serviceIdentifier": service_identifier,
            "serviceBezeichnung": titel,
            "artDerNachricht": "JSON Struktur aus Editor",
            "schemaUri": schema_uri
            or f"https://<dein-github-user>.github.io/fit-connect-schemata/{schema_id.lower()}/schema.jsonschema.json",
        },
        "nachrichtImJsonFormat": nachricht,
    }

    return json.dumps(ergebnis, ensure_ascii=False, indent=2)
