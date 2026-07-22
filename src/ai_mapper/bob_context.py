"""Domänen-Kontext über die LeiKa-Nummer: findet die fachlich passenden
BOB-Bausteine ("Baukasten optimierter Bausteinelemente"), statt sie zu raten.

FIM pflegt keine offizielle Zuordnungstabelle LeiKa -> BOB-Bausteine (recherchiert
am 2026-07-22, FIM verweist auf Einzelfallprüfung durch Modellierer). Stattdessen
wird empirisch vorgegangen und live gegen die echte API verifiziert:

1. LeiKa-Nummer -> Leistungsbeschreibung abrufen (Rechtsgrundlage, Bezeichnung,
   OZG-Themenfeld) über /api/v1/leistung-steckbriefe.
2. Mit Rechtsgrundlage/Bezeichnung nach ähnlichen, bereits freigegebenen
   FIM-Referenzschemata suchen (/api/v1/schemas).
   Verifiziertes Beispiel: LeiKa 99003002022000 ("Belehrung nach dem
   Infektionsschutzgesetz Bescheinigung", Rechtsgrundlage "§ 43 Absatz 1
   Infektionsschutzgesetz (IfSG)") liefert als Top-Treffer exakt das echte
   Referenzschema S00000253 ("Antrag Bescheinigung Belehrung
   Infektionsschutzgesetz").
3. Aus diesen ähnlichen Schemata die tatsächlich verwendeten BOB-Bausteine
   extrahieren (Datenfelder/-gruppen im Nummernkreis 60000) und als priorisierte
   Kandidaten fürs Matching bereitstellen.

Dieser Kontext funktioniert komplett ohne LLM - reine FIM-API-Aufrufe.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Iterator, List, Optional, Tuple

from .fim_client import XDF2_NS, FimClient
from .models import FimKandidat, LeikaKontext

BOB_NUMMERNKREIS = "60000"


def _datenfelder_mit_gruppe(
    elem: ET.Element, aktuelle_gruppe: Optional[Tuple[str, str]] = None
) -> Iterator[Tuple[ET.Element, Optional[Tuple[str, str]]]]:
    """Rekursiver Baum-Walk: liefert jedes <datenfeld> zusammen mit der ID/Version
    der unmittelbar umschließenden <datenfeldgruppe> (falls vorhanden).

    Wichtig für die spätere FORMCYCLE-Bindung: ein Datenfeld allein reicht nicht -
    die Gruppe, in der es im Referenzschema steht (z. B. G00002115 "Antragsteller -
    Natürliche Person"), muss mit übergeben werden.
    """
    tag = elem.tag.rsplit("}", 1)[-1]

    if tag == "datenfeldgruppe":
        ident = elem.find(f"{{{XDF2_NS}}}identifikation")
        if ident is not None:
            gruppe_id = ident.find(f"{{{XDF2_NS}}}id").text
            gruppe_version = ident.find(f"{{{XDF2_NS}}}version").text
            aktuelle_gruppe = (gruppe_id, gruppe_version)

    if tag == "datenfeld":
        yield elem, aktuelle_gruppe
        return  # Datenfelder haben keine weiteren datenfeld-Kinder

    for kind in elem:
        yield from _datenfelder_mit_gruppe(kind, aktuelle_gruppe)


def _nummernkreis_von_id(fim_id: str) -> str:
    """Nummernkreis = die ersten 5 Ziffern des numerischen ID-Teils.

    Gilt unabhängig von der Gesamtlänge (XDF2 vs. XDF3 nutzen unterschiedlich
    viele Nachkommastellen, das Präfix bleibt gleich): F60000227 -> "60000",
    F60000000227 -> "60000", F00000013 -> "00000".
    """
    ziffern = re.sub(r"^[A-Za-z]+", "", fim_id)
    return ziffern[:5]


def resolve_leika_kontext(leika_nummer: str, fim_client: FimClient) -> LeikaKontext:
    leistung = fim_client.get_leistung(leika_nummer)
    if leistung is None:
        return LeikaKontext(leika_nummer=leika_nummer)

    ozg = leistung.get("ozg") or {}

    kontext = LeikaKontext(
        leika_nummer=leika_nummer,
        leistungsbezeichnung=leistung.get("leistungsbezeichnung"),
        rechtsgrundlagen=leistung.get("rechtsgrundlagen"),
        ozg_themenfeld=ozg.get("themenfeld_label"),
    )

    for query in filter(None, [kontext.rechtsgrundlagen, kontext.leistungsbezeichnung]):
        schemas = fim_client.search_schemas(query, limit=3)
        for s in schemas:
            schema_ref = f"{s['fim_id']}/{s['fim_version']}"
            if schema_ref not in kontext.aehnliche_schemas:
                kontext.aehnliche_schemas.append(schema_ref)
        if kontext.aehnliche_schemas:
            break  # Rechtsgrundlage hat Vorrang, nur bei leerem Ergebnis Fallback nutzen

    return kontext


def harvest_bob_bausteine(kontext: LeikaKontext, fim_client: FimClient, max_schemas: int = 3) -> List[FimKandidat]:
    """Lädt die ähnlichen Schemata und extrahiert ihre BOB-Datenfelder (Nummernkreis 60000)."""
    kandidaten: List[FimKandidat] = []
    gesehen = set()

    for schema_ref in kontext.aehnliche_schemas[:max_schemas]:
        fim_id, fim_version = schema_ref.split("/")
        try:
            root = fim_client.get_schema_xdf_root(fim_id, fim_version)
        except Exception:
            continue

        for feld, gruppe in _datenfelder_mit_gruppe(root):
            ident = feld.find(f"{{{XDF2_NS}}}identifikation")
            if ident is None:
                continue
            feld_id = ident.find(f"{{{XDF2_NS}}}id").text
            if _nummernkreis_von_id(feld_id) != BOB_NUMMERNKREIS or feld_id in gesehen:
                continue
            gesehen.add(feld_id)

            name_elem = feld.find(f"{{{XDF2_NS}}}name")
            datentyp_elem = feld.find(f"{{{XDF2_NS}}}datentyp/code")
            feldart_elem = feld.find(f"{{{XDF2_NS}}}feldart/code")
            definition_elem = feld.find(f"{{{XDF2_NS}}}definition")

            kandidaten.append(
                FimKandidat(
                    namespace="baukasten",
                    fim_id=feld_id,
                    fim_version=ident.find(f"{{{XDF2_NS}}}version").text,
                    name=name_elem.text if name_elem is not None else feld_id,
                    definition=definition_elem.text if definition_elem is not None else None,
                    freigabe_status=6,
                    feldart=feldart_elem.text if feldart_elem is not None else None,
                    datentyp=datentyp_elem.text if datentyp_elem is not None else None,
                    aus_domain_kontext=True,
                    gruppe_id=gruppe[0] if gruppe else None,
                    gruppe_version=gruppe[1] if gruppe else None,
                )
            )

    return kandidaten
