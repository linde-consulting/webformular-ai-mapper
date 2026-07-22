"""Orchestriert den gesamten Ablauf: Formular -> FIM-Suche -> Matching ->
Schema-Bau -> XSD -> Formcycle-Template -> Mapping-Report.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import schema_builder
from .bob_context import harvest_bob_bausteine, resolve_leika_kontext
from .fim_client import FimClient
from .formcycle_export import build_formcycle_template
from .matcher import match_feld
from .models import FimKandidat, FormularInput, LeikaKontext, MatchErgebnis, MappingReport


@dataclass
class MappingErgebnis:
    report: MappingReport
    xdf_xml: str
    xsd_xml: str
    json_schema: str
    formcycle_json: str


def _namespace_slug(titel: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", titel.lower()).strip("-")


def run_pipeline(formular: FormularInput, fim_client: FimClient) -> MappingErgebnis:
    schema_namespace = f"{_namespace_slug(formular.titel)}:{formular.leika_nummer or 'ohne-leika'}"

    leika_kontext: Optional[LeikaKontext] = None
    domain_kandidaten: List[FimKandidat] = []
    if formular.leika_nummer:
        leika_kontext = resolve_leika_kontext(formular.leika_nummer, fim_client)
        domain_kandidaten = harvest_bob_bausteine(leika_kontext, fim_client)

    matches: List[MatchErgebnis] = []
    elemente_je_feld: Dict[str, ET.Element] = {}

    for feld in formular.felder:
        kandidaten = domain_kandidaten + fim_client.search_fields(feld.label)
        kandidat, confidence, begruendung = match_feld(feld, kandidaten)

        if kandidat is not None:
            datenfeld_elem = fim_client.get_field_datenfeld_xml(
                kandidat.namespace, kandidat.fim_id, kandidat.fim_version
            )
            match = MatchErgebnis(
                feld_id=feld.id,
                label=feld.label,
                status="REUSE",
                confidence=confidence,
                begruendung=begruendung,
                fim_kandidat=kandidat,
            )
        else:
            datenfeld_elem = schema_builder.build_neues_datenfeld(feld, schema_namespace)
            neue_id = datenfeld_elem.find(
                f"{{{schema_builder.XDF2_NS}}}identifikation/{{{schema_builder.XDF2_NS}}}id"
            ).text
            match = MatchErgebnis(
                feld_id=feld.id,
                label=feld.label,
                status="NEU",
                confidence=confidence,
                begruendung=begruendung,
                neue_id=neue_id,
            )

        matches.append(match)
        elemente_je_feld[feld.id] = datenfeld_elem

    gruppen: Dict[str, List[Tuple[ET.Element, bool]]] = {}
    felder_ohne_gruppe: List[Tuple[ET.Element, bool]] = []
    for feld in formular.felder:
        elem = elemente_je_feld[feld.id]
        if feld.abschnitt:
            gruppen.setdefault(feld.abschnitt, []).append((elem, feld.pflichtfeld))
        else:
            felder_ohne_gruppe.append((elem, feld.pflichtfeld))

    schema_root = schema_builder.build_stammdatenschema(
        titel=formular.titel,
        schema_namespace=schema_namespace,
        felder_mit_xml=felder_ohne_gruppe,
        gruppen=gruppen,
        leika_nummer=formular.leika_nummer,
    )
    xdf_xml = schema_builder.to_xml_string(schema_root)

    xsd_xml = fim_client.convert_xdf2_to_xsd(xdf_xml)
    json_schema = fim_client.convert_xdf2_to_json_schema(xdf_xml)

    schema_id = schema_root.find(
        f"{{{schema_builder.XDF2_NS}}}stammdatenschema/{{{schema_builder.XDF2_NS}}}identifikation/{{{schema_builder.XDF2_NS}}}id"
    ).text

    formcycle_json = build_formcycle_template(
        schema_id=schema_id,
        schema_version="1.0",
        titel=formular.titel,
        felder=formular.felder,
        matches=matches,
        leika_nummer=formular.leika_nummer,
    )

    report = MappingReport(
        schema_id=schema_id,
        schema_version="1.0",
        titel=formular.titel,
        leika_nummer=formular.leika_nummer,
        leika_kontext=leika_kontext,
        matches=matches,
    )

    return MappingErgebnis(
        report=report,
        xdf_xml=xdf_xml,
        xsd_xml=xsd_xml,
        json_schema=json_schema,
        formcycle_json=formcycle_json,
    )


def render_mapping_report_markdown(ergebnis: MappingErgebnis) -> str:
    r = ergebnis.report
    zeilen = [
        f"# Mapping-Report: {r.titel}",
        "",
        f"- Schema-ID: `{r.schema_id}` (Version {r.schema_version})",
        f"- LeiKa-Nummer: {r.leika_nummer or '-'}",
    ]

    kontext = r.leika_kontext
    if kontext and (kontext.rechtsgrundlagen or kontext.aehnliche_schemas):
        zeilen += [
            "",
            "## LeiKa-Domain-Kontext",
            f"- Leistungsbezeichnung: {kontext.leistungsbezeichnung or '-'}",
            f"- Rechtsgrundlage: {kontext.rechtsgrundlagen or '-'}",
            f"- OZG-Themenfeld: {kontext.ozg_themenfeld or '-'}",
            f"- Ähnliche FIM-Referenzschemata (Quelle der priorisierten BOB-Bausteine): "
            f"{', '.join(kontext.aehnliche_schemas) if kontext.aehnliche_schemas else '(keine gefunden)'}",
        ]

    zeilen += [
        "",
        "| Feld | Status | Quelle | Confidence | Begründung |",
        "|---|---|---|---|---|",
    ]
    for m in r.matches:
        if m.status == "REUSE" and m.fim_kandidat:
            herkunft = "BOB-Domain-Kontext" if m.fim_kandidat.aus_domain_kontext else "generische Suche"
            quelle = f"{m.fim_kandidat.namespace}/{m.fim_kandidat.fim_id}/{m.fim_kandidat.fim_version} ({herkunft})"
        else:
            quelle = f"neu: {m.neue_id}"
        zeilen.append(
            f"| {m.label} | {m.status} | {quelle} | {m.confidence:.2f} | {m.begruendung} |"
        )
    return "\n".join(zeilen) + "\n"
