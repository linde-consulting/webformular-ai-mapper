"""Erzeugt die zweite Ausgabedatei: XML-Template für die Objektinitialisierung
im FORMCYCLE-FIT-Connect-Plugin-Editor.

WICHTIG: Das interne XML-Format dieses Plugin-Editors ist öffentlich nicht
dokumentiert (recherchiert am 2026-07-14 — weder FORMCYCLE-Wiki noch die
MACH-formsolutions-Dokumentation legen die exakte Struktur offen). Dieses
Template orientiert sich an der dokumentierten FIT-Connect-URN-Konvention für
Fachdatenschemata (siehe Ausgangslage.docx / MACH-formsolutions-Doku:
"urn:de:<land>:<produkt>:...") und muss mit einem echten FORMCYCLE-Export
abgeglichen werden, sobald einer vorliegt.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional

from .models import MatchErgebnis

ANNAHME_KOMMENTAR = (
    " ANNAHME / TEMPLATE - kein 1:1 abgeglichener FORMCYCLE-Export. "
    "Das interne XML-Format des FORMCYCLE FIT-Connect-Plugins zur "
    "Schema-Objektinitialisierung ist oeffentlich nicht dokumentiert. "
    "Struktur orientiert sich an der FIT-Connect-URN-Konvention "
    "(vgl. Ausgangslage.docx). Bitte mit echtem FORMCYCLE-Export abgleichen. "
)


def build_formcycle_template(
    schema_id: str,
    schema_version: str,
    titel: str,
    matches: List[MatchErgebnis],
    leika_nummer: Optional[str] = None,
    schema_uri: Optional[str] = None,
) -> str:
    namespace_slug = titel.lower().replace(" ", "-")
    urn = f"urn:linde-consulting:fit-connect:schema:{schema_id.lower()}_{schema_version}"

    root = ET.Element("fitConnectPluginConfig")
    fachdaten = ET.SubElement(root, "fachdatenSchema")
    ET.SubElement(fachdaten, "urn").text = urn
    ET.SubElement(fachdaten, "schemaUri").text = schema_uri or (
        f"https://<dein-github-user>.github.io/fit-connect-schemata/{namespace_slug}/schema.xsd"
    )
    if leika_nummer:
        ET.SubElement(fachdaten, "leikaSchluessel").text = leika_nummer
    ET.SubElement(fachdaten, "bezeichnung").text = titel

    mapping = ET.SubElement(root, "feldMapping")
    for m in matches:
        feld_id = m.fim_kandidat.fim_id if m.status == "REUSE" and m.fim_kandidat else m.neue_id
        namespace = m.fim_kandidat.namespace if m.status == "REUSE" and m.fim_kandidat else "eigene"
        ET.SubElement(
            mapping,
            "feld",
            {
                "formularFeldId": m.feld_id,
                "xdfDatenfeldId": feld_id or "",
                "xdfNamespace": namespace,
                "quelle": m.status,
            },
        ).text = m.label

    body = ET.tostring(root, encoding="unicode")
    return f"<?xml version='1.0' encoding='utf-8'?>\n<!--{ANNAHME_KOMMENTAR}-->\n{body}"
