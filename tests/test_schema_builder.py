import xml.etree.ElementTree as ET

from ai_mapper.models import Formularfeld
from ai_mapper.schema_builder import (
    XDF2_NS,
    build_neues_datenfeld,
    build_stammdatenschema,
    to_xml_string,
)


def test_build_neues_datenfeld_hat_id_im_9er_nummernkreis():
    feld = Formularfeld(id="nachname", label="Nachname", typ="text", pflichtfeld=True)
    elem = build_neues_datenfeld(feld, "test-namespace")

    id_text = elem.find(f"{{{XDF2_NS}}}identifikation/{{{XDF2_NS}}}id").text
    assert id_text.startswith("F9")
    assert len(id_text) == 9  # "F9" + 7 Ziffern


def test_build_neues_datenfeld_ist_deterministisch():
    feld = Formularfeld(id="nachname", label="Nachname", typ="text")
    elem1 = build_neues_datenfeld(feld, "ns")
    elem2 = build_neues_datenfeld(feld, "ns")
    id1 = elem1.find(f"{{{XDF2_NS}}}identifikation/{{{XDF2_NS}}}id").text
    id2 = elem2.find(f"{{{XDF2_NS}}}identifikation/{{{XDF2_NS}}}id").text
    assert id1 == id2


def test_stammdatenschema_enthaelt_alle_felder():
    felder = [
        Formularfeld(id="a", label="Nachname", typ="text"),
        Formularfeld(id="b", label="Geburtsdatum", typ="datum"),
    ]
    elemente = [(build_neues_datenfeld(f, "ns"), f.pflichtfeld) for f in felder]

    root = build_stammdatenschema(
        titel="Testschema", schema_namespace="ns", felder_mit_xml=elemente, gruppen={}
    )
    xml_str = to_xml_string(root)

    assert "Nachname" in xml_str
    assert "Geburtsdatum" in xml_str
    assert xml_str.startswith("<?xml version='1.0' encoding='utf-8'?>")

    # Muss gültiges XML sein
    ET.fromstring(xml_str.split("\n", 1)[1])
