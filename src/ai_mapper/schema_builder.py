"""Deterministischer Bau des XDatenfelder-2.0-Referenzschemas (kein LLM).

Format wurde live gegen die FIM-Portal-API verifiziert: der hier erzeugte Baum
wird von POST /tools/xdf2-xsd-converter akzeptiert und liefert eine gültige XSD.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .fim_client import XDF2_NS
from .models import FeldTyp, Formularfeld

# Ein <struktur>-Element wrappt laut FIM-Datenmodell IMMER genau ein Kind-Element
# (ein <datenfeld> ODER eine <datenfeldgruppe>) zusammen mit seiner Kardinalität
# (<anzahl>, z. B. "1:1" für Pflicht, "0:1" für optional). Für mehrere Geschwister
# auf derselben Ebene braucht es mehrere <struktur>-Geschwister-Elemente - NICHT
# mehrere Kinder in einem gemeinsamen <enthaelt>. Verifiziert anhand eines echten,
# freigegebenen FIM-Referenzschemas (S00000092): <enthaelt>-Anzahl entspricht dort
# exakt der Summe aus <datenfeld>- und <datenfeldgruppe>-Elementen.

NSMAP = {"ns0": XDF2_NS}

# Webform-Feldtyp -> (xdatenfelder.datentyp-Code, xdatenfelder.feldart-Code)
# Codes verifiziert per Stichprobe realer, freigegebener FIM-Datenfelder.
DATENTYP_MAPPING: Dict[FeldTyp, tuple] = {
    "text": ("text", "input"),
    "mehrzeilig": ("text", "input"),
    "email": ("text", "input"),
    "tel": ("text", "input"),
    "zahl": ("num", "input"),
    "ganzzahl": ("num_int", "input"),
    "betrag": ("num_currency", "input"),
    "datum": ("date", "input"),
    "checkbox": ("bool", "input"),
    "datei": ("file", "input"),
    "auswahl": ("text", "select"),
}


def _tag(local: str) -> str:
    return f"{{{XDF2_NS}}}{local}"


def neue_feld_id(schema_namespace: str, feld_id: str) -> str:
    """Deterministische, FIM-ID-konforme ID im selbst vergebenen Nummernkreis '9'.

    FIM verlangt ein Präfix-Zeichen + Ziffern (z. B. F00000013). Da eigene Felder
    nicht bei der Bundesredaktion registriert sind, wird bewusst der Nummernkreis
    '9xxxxxxx' verwendet, um Kollisionen mit echten FIM-IDs zu vermeiden.
    """
    digest = zlib.crc32(f"{schema_namespace}:{feld_id}".encode("utf-8")) % 10_000_000
    return f"F9{digest:07d}"


def neues_schema_id(schema_namespace: str) -> str:
    digest = zlib.crc32(schema_namespace.encode("utf-8")) % 10_000_000
    return f"S9{digest:07d}"


def _status_element(parent: ET.Element, tag: str, code: str, list_uri: str, list_version: str = "1.0") -> None:
    el = ET.SubElement(parent, _tag(tag), {"listURI": list_uri, "listVersionID": list_version})
    ET.SubElement(el, "code").text = code


def build_neues_datenfeld(feld: Formularfeld, schema_namespace: str) -> ET.Element:
    """Erzeugt ein neues <ns0:datenfeld>-Element für ein Feld ohne FIM-Treffer."""
    datentyp_code, feldart_code = DATENTYP_MAPPING[feld.typ]
    feld_id = neue_feld_id(schema_namespace, feld.id)

    datenfeld = ET.Element(_tag("datenfeld"))
    ident = ET.SubElement(datenfeld, _tag("identifikation"))
    ET.SubElement(ident, _tag("id")).text = feld_id
    ET.SubElement(ident, _tag("version")).text = "1.0"

    ET.SubElement(datenfeld, _tag("name")).text = feld.label
    ET.SubElement(datenfeld, _tag("bezeichnungEingabe")).text = feld.label
    ET.SubElement(datenfeld, _tag("bezeichnungAusgabe")).text = feld.label
    if feld.hilfetext:
        ET.SubElement(datenfeld, _tag("hilfetextEingabe")).text = feld.hilfetext

    _status_element(datenfeld, "status", "aktiv", "urn:xoev-de:fim:codeliste:xdatenfelder.status")
    _status_element(
        datenfeld, "schemaelementart", "HAR", "urn:xoev-de:fim:codeliste:xdatenfelder.schemaelementart"
    )
    _status_element(datenfeld, "feldart", feldart_code, "urn:xoev-de:fim:codeliste:xdatenfelder.feldart")
    _status_element(datenfeld, "datentyp", datentyp_code, "urn:xoev-de:fim:codeliste:xdatenfelder.datentyp")

    if feld.optionen:
        praezisierung = ET.SubElement(datenfeld, _tag("praezisierung"))
        praezisierung.text = ", ".join(feld.optionen)

    return datenfeld


def _neue_gruppe_id(schema_namespace: str, name: str) -> str:
    digest = zlib.crc32(f"{schema_namespace}:gruppe:{name}".encode("utf-8")) % 10_000_000
    return f"G9{digest:07d}"


def _anzahl_fuer(pflichtfeld: bool) -> str:
    return "1:1" if pflichtfeld else "0:1"


def _append_struktur(parent: ET.Element, kind_elem: ET.Element, anzahl: str = "1:1") -> None:
    """Hängt ein <struktur>-Geschwisterelement an, das genau ein Kind wrappt."""
    struktur = ET.SubElement(parent, _tag("struktur"))
    ET.SubElement(struktur, _tag("anzahl")).text = anzahl
    enthaelt = ET.SubElement(struktur, _tag("enthaelt"))
    enthaelt.append(kind_elem)


def build_stammdatenschema(
    titel: str,
    schema_namespace: str,
    felder_mit_xml: List[Tuple[ET.Element, bool]],
    gruppen: Dict[str, List[Tuple[ET.Element, bool]]],
    beschreibung: str = "",
    leika_nummer: Optional[str] = None,
) -> ET.Element:
    """Komponiert das vollständige xdf2-Stammdatenschema-Dokument."""
    schema_id = neues_schema_id(schema_namespace)

    root = ET.Element(_tag("xdatenfelder.stammdatenschema.0102"))
    header = ET.SubElement(root, _tag("header"))
    ET.SubElement(header, _tag("nachrichtID")).text = "ai-mapper-export"
    ET.SubElement(header, _tag("erstellungszeitpunkt")).text = datetime.now(timezone.utc).isoformat()

    schema = ET.SubElement(root, _tag("stammdatenschema"))
    ident = ET.SubElement(schema, _tag("identifikation"))
    ET.SubElement(ident, _tag("id")).text = schema_id
    ET.SubElement(ident, _tag("version")).text = "1.0"

    ET.SubElement(schema, _tag("name")).text = titel
    ET.SubElement(schema, _tag("bezeichnungEingabe")).text = titel
    ET.SubElement(schema, _tag("bezeichnungAusgabe")).text = titel
    ET.SubElement(schema, _tag("beschreibung")).text = (
        beschreibung or f"Automatisch mit ai-mapper erzeugtes Referenzschema für '{titel}'."
    )
    if leika_nummer:
        ET.SubElement(schema, _tag("bezug")).text = f"LeiKa {leika_nummer}"

    _status_element(schema, "status", "aktiv", "urn:xoev-de:fim:codeliste:xdatenfelder.status")
    _status_element(
        schema,
        "ableitungsmodifikationenStruktur",
        "3",
        "urn:xoev-de:fim:codeliste:xdatenfelder.ableitungsmodifikationenStruktur",
    )
    _status_element(
        schema,
        "ableitungsmodifikationenRepraesentation",
        "1",
        "urn:xoev-de:fim:codeliste:xdatenfelder.ableitungsmodifikationenRepraesentation",
    )

    for gruppen_name, gruppen_felder in gruppen.items():
        gruppe = ET.Element(_tag("datenfeldgruppe"))
        g_ident = ET.SubElement(gruppe, _tag("identifikation"))
        ET.SubElement(g_ident, _tag("id")).text = _neue_gruppe_id(schema_namespace, gruppen_name)
        ET.SubElement(g_ident, _tag("version")).text = "1.0"
        ET.SubElement(gruppe, _tag("name")).text = gruppen_name
        ET.SubElement(gruppe, _tag("bezeichnungEingabe")).text = gruppen_name
        ET.SubElement(gruppe, _tag("bezeichnungAusgabe")).text = gruppen_name
        _status_element(gruppe, "status", "aktiv", "urn:xoev-de:fim:codeliste:xdatenfelder.status")
        _status_element(
            gruppe, "schemaelementart", "HAR", "urn:xoev-de:fim:codeliste:xdatenfelder.schemaelementart"
        )
        for feld_elem, pflichtfeld in gruppen_felder:
            _append_struktur(gruppe, feld_elem, _anzahl_fuer(pflichtfeld))

        _append_struktur(schema, gruppe, "1:1")

    for feld_elem, pflichtfeld in felder_mit_xml:
        _append_struktur(schema, feld_elem, _anzahl_fuer(pflichtfeld))

    return root


def to_xml_string(root: ET.Element) -> str:
    tree_str = ET.tostring(root, encoding="unicode")
    return f"<?xml version='1.0' encoding='utf-8'?>\n{tree_str}"
