"""Import echter FORMCYCLE-Formular-Exporte (JSON aus dem Formular-Editor,
Menü "Formular exportieren").

Struktur (verifiziert anhand eines echten Exports, examples/webform-Neues
Formular.json): Top-Level `items` ist die flache Liste aller Editor-Elemente
dieses Formulars (`className` + `properties`), `base` sind nur die
Editor-Vorlagen/Defaults pro Feldtyp (keine Instanzdaten). Layout-/Deko-Elemente
(XHeader, XPage, XFooter, XButtonList, XImage, XLine, XSpacer, XCaptcha, ...)
werden übersprungen; nur echte Eingabefelder werden übernommen.

Erkennung ggü. dem eigenen FormularInput-JSON: Formcycle-Exporte haben einen
Top-Level-Key `items`, das eigene Format hat stattdessen `felder`.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from .models import Formularfeld

# Formcycle-className -> unser FeldTyp. Nicht gelistete Klassen (Layout/Deko)
# werden beim Import ignoriert.
CLASSNAME_MAPPING: Dict[str, str] = {
    "XTextField": "text",
    "XTextfieldAdvanced": "text",
    "XTextArea": "mehrzeilig",
    "XSelect": "auswahl",
    "XDatalistAdvanced": "auswahl",
    "XCheckbox": "checkbox",
    "XUpload": "datei",
    "XAppointment": "datum",
}

# Feinere Typisierung von Textfeldern über datatype/datatypeHint, falls gesetzt.
DATENTYP_HINWEIS_MAPPING: Dict[str, str] = {
    "email": "email",
    "tel": "tel",
    "phone": "tel",
    "currency": "betrag",
    "int": "ganzzahl",
    "integer": "ganzzahl",
    "float": "zahl",
    "number": "zahl",
}


class FormcycleImportError(ValueError):
    pass


def ist_formcycle_export(daten: dict) -> bool:
    return isinstance(daten, dict) and "items" in daten and "felder" not in daten


def formular_titel(daten: dict) -> Optional[str]:
    return daten.get("title") or None


def _label_bereinigen(html_label: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_label or "")
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip()).strip("-").lower()
    return slug or "feld"


def parse_formcycle_export(daten: dict) -> List[Formularfeld]:
    items = daten.get("items", [])
    id_zu_item = {
        it["properties"]["id"]: it for it in items if "id" in it.get("properties", {})
    }

    def _abschnitt_fuer(item: dict) -> Optional[str]:
        """Nächstgelegene übergeordnete XPage (Titel) oder XFieldSet (Legende)."""
        parentid = item["properties"].get("parentid")
        gesehen = set()
        while parentid and parentid not in gesehen:
            gesehen.add(parentid)
            eltern = id_zu_item.get(parentid)
            if eltern is None:
                break
            klass = eltern.get("className")
            props = eltern.get("properties", {})
            if klass == "XFieldSet" and props.get("legend"):
                return props["legend"]
            if klass == "XPage" and (props.get("header") or props.get("name")):
                return props.get("header") or props.get("name")
            parentid = props.get("parentid")
        return None

    felder: List[Formularfeld] = []
    vergebene_ids: Dict[str, int] = {}

    for item in items:
        klass = item.get("className")
        if klass not in CLASSNAME_MAPPING:
            continue
        props = item.get("properties", {})

        typ = CLASSNAME_MAPPING[klass]
        if klass in ("XTextField", "XTextfieldAdvanced"):
            hinweis = (props.get("datatypeHint") or props.get("datatype") or "").lower()
            typ = DATENTYP_HINWEIS_MAPPING.get(hinweis, typ)

        label = _label_bereinigen(props.get("label", "")) or props.get("name") or "unbenannt"

        # Technischer Name unverändert übernehmen (z. B. "tf1_st_Vorname") - wird
        # später für die %-Variablen-Bindung im FORMCYCLE-Export gebraucht.
        technischer_name = props.get("name") or props.get("id")

        feld_id = _slugify(props.get("aliasname") or props.get("name") or props.get("id", "feld"))
        if feld_id in vergebene_ids:
            vergebene_ids[feld_id] += 1
            feld_id = f"{feld_id}-{vergebene_ids[feld_id]}"
        else:
            vergebene_ids[feld_id] = 1

        optionen = None
        if props.get("options"):
            optionen = [o["text"] for o in props["options"] if o.get("text")] or None

        felder.append(
            Formularfeld(
                id=feld_id,
                label=label,
                typ=typ,  # type: ignore[arg-type]
                pflichtfeld=str(props.get("required", "0")) in ("1", "true", "True"),
                optionen=optionen,
                abschnitt=_abschnitt_fuer(item),
                hilfetext=_label_bereinigen(props.get("helptext", "")) or None,
                technischer_name=technischer_name,
            )
        )

    if not felder:
        raise FormcycleImportError(
            "Keine unterstützten Formularfelder im FORMCYCLE-Export gefunden. "
            f"Unterstützte Feldtypen: {', '.join(CLASSNAME_MAPPING)}."
        )

    return felder
