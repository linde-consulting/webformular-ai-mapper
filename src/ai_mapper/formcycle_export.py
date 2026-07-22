"""Erzeugt die zweite Ausgabedatei: JSON-Template für die Objekt-/Gruppen-
Initialisierung im FORMCYCLE-FIT-Connect-Plugin-Editor.

WICHTIG: Das interne Format dieses Plugin-Editors ist öffentlich nicht
dokumentiert (recherchiert am 2026-07-14/2026-07-22 - weder FORMCYCLE-Wiki noch
die MACH-formsolutions-Doku legen die exakte Struktur offen; auch das dazu
verlinkte YouTube-Video hat weder Untertitel noch Beschreibung, ein Transkript
war nicht extrahierbar). Dieses Template setzt konzeptionell um, was der Nutzer
beschrieben hat und live an einem echten FIM-Schema verifiziert wurde:

- Referenzschema-Felder sind über eine Datenfeldgruppe strukturiert (z. B.
  gehört F60000228 "Vornamen" zur Gruppe G00002115 "Antragsteller - Natürliche
  Person" - verifiziert gegen die echte FIM-API, siehe test_bob_context.py).
  Diese Gruppenzugehörigkeit muss im Editor mit initialisiert werden, nicht nur
  das einzelne Feld.
- Jedes FIM-Datenfeld wird an den TECHNISCHEN Namen des Formularfelds im
  Webformular gebunden (z. B. FORMCYCLE-Feldname "tf1_st_Vorname"), referenziert
  über FORMCYCLE-typische %-Variablen-Syntax ("%tf1_st_Vorname%").

Muss mit einem echten FORMCYCLE-Export/-Editor-Zustand abgeglichen werden,
sobald einer mit dieser Objektinitialisierung vorliegt.
"""
from __future__ import annotations

import json
from typing import List, Optional

from .models import Formularfeld, MatchErgebnis

ANNAHME_HINWEIS = (
    "ANNAHME / TEMPLATE - kein 1:1 abgeglichener FORMCYCLE-Zustand. Das interne "
    "Format des FORMCYCLE FIT-Connect-Plugins zur Schema-/Gruppen-Objektinitialisierung "
    "ist oeffentlich nicht dokumentiert. Struktur bildet konzeptionell ab: (1) "
    "Datenfeldgruppen-Zugehoerigkeit aus dem Referenzschema, (2) Bindung jedes "
    "FIM-Datenfelds an den technischen Formularfeld-Namen ueber %-Variablen-Syntax. "
    "Bitte mit echtem FORMCYCLE-Zustand abgleichen."
)


def _formcycle_variable(technischer_name: str) -> str:
    return f"%{technischer_name}%"


def build_formcycle_template(
    schema_id: str,
    schema_version: str,
    titel: str,
    felder: List[Formularfeld],
    matches: List[MatchErgebnis],
    leika_nummer: Optional[str] = None,
    schema_uri: Optional[str] = None,
) -> str:
    namespace_slug = titel.lower().replace(" ", "-")
    urn = f"urn:linde-consulting:fit-connect:schema:{schema_id.lower()}_{schema_version}"
    technischer_name_je_feld = {f.id: (f.technischer_name or f.id) for f in felder}

    gruppen: dict = {}
    ungruppiert: list = []

    for m in matches:
        formcycle_var = _formcycle_variable(technischer_name_je_feld.get(m.feld_id, m.feld_id))

        if m.status == "REUSE" and m.fim_kandidat:
            feld_eintrag = {
                "fimFeldId": m.fim_kandidat.fim_id,
                "fimFeldVersion": m.fim_kandidat.fim_version,
                "fimNamespace": m.fim_kandidat.namespace,
                "formcycleVariable": formcycle_var,
                "quelle": "REUSE",
                "label": m.label,
            }
            gruppe_id = m.fim_kandidat.gruppe_id
        else:
            feld_eintrag = {
                "fimFeldId": m.neue_id,
                "fimFeldVersion": "1.0",
                "fimNamespace": "eigene",
                "formcycleVariable": formcycle_var,
                "quelle": "NEU",
                "label": m.label,
            }
            gruppe_id = None

        if gruppe_id:
            gruppe = gruppen.setdefault(
                gruppe_id,
                {"fimGruppeId": gruppe_id, "fimGruppeVersion": m.fim_kandidat.gruppe_version, "felder": []},
            )
            gruppe["felder"].append(feld_eintrag)
        else:
            ungruppiert.append(feld_eintrag)

    ergebnis = {
        "_hinweis": ANNAHME_HINWEIS,
        "fachdatenSchema": {
            "urn": urn,
            "schemaUri": schema_uri
            or f"https://<dein-github-user>.github.io/fit-connect-schemata/{namespace_slug}/schema.xsd",
            "leikaSchluessel": leika_nummer,
            "bezeichnung": titel,
        },
        "gruppenInitialisierung": list(gruppen.values()),
        "ungruppierteFelder": ungruppiert,
    }

    return json.dumps(ergebnis, ensure_ascii=False, indent=2)
