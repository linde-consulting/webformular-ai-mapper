"""Live-Smoke-Tests gegen die echte, öffentliche FIM-Portal-API.

Diese Tests brauchen Internetzugriff. Sie prüfen nur, dass die Endpunkte
weiterhin wie erwartet antworten - keine tiefergehenden Assertions.
"""
import pytest

from ai_mapper.fim_client import FimClient


@pytest.fixture
def client():
    return FimClient()


def test_search_fields_findet_kandidaten(client):
    kandidaten = client.search_fields("Familienname")
    assert len(kandidaten) > 0
    assert any(k.datentyp == "text" for k in kandidaten)


def test_get_field_datenfeld_xml(client):
    kandidaten = client.search_fields("Familienname")
    k = kandidaten[0]
    elem = client.get_field_datenfeld_xml(k.namespace, k.fim_id, k.fim_version)
    assert elem.tag.endswith("}datenfeld")


def test_convert_xdf2_to_xsd_minimalbeispiel(client):
    minimal_xdf = (
        "<?xml version='1.0' encoding='utf-8'?>"
        "<ns0:xdatenfelder.stammdatenschema.0102 xmlns:ns0=\"urn:xoev-de:fim:standard:xdatenfelder_2\">"
        "<ns0:header><ns0:nachrichtID>test</ns0:nachrichtID>"
        "<ns0:erstellungszeitpunkt>2026-01-01T00:00:00+00:00</ns0:erstellungszeitpunkt></ns0:header>"
        "<ns0:stammdatenschema><ns0:identifikation><ns0:id>S90000001</ns0:id>"
        "<ns0:version>1.0</ns0:version></ns0:identifikation><ns0:name>Test</ns0:name>"
        "<ns0:bezeichnungEingabe>Test</ns0:bezeichnungEingabe>"
        "<ns0:bezeichnungAusgabe>Test</ns0:bezeichnungAusgabe>"
        "<ns0:beschreibung>Test</ns0:beschreibung>"
        "<ns0:status listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.status\" listVersionID=\"1.0\">"
        "<code>aktiv</code></ns0:status>"
        "<ns0:ableitungsmodifikationenStruktur "
        "listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.ableitungsmodifikationenStruktur\" "
        "listVersionID=\"1.0\"><code>3</code></ns0:ableitungsmodifikationenStruktur>"
        "<ns0:ableitungsmodifikationenRepraesentation "
        "listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.ableitungsmodifikationenRepraesentation\" "
        "listVersionID=\"1.0\"><code>1</code></ns0:ableitungsmodifikationenRepraesentation>"
        "<ns0:struktur><ns0:anzahl>1:1</ns0:anzahl><ns0:enthaelt>"
        "<ns0:datenfeld><ns0:identifikation><ns0:id>F90000001</ns0:id>"
        "<ns0:version>1.0</ns0:version></ns0:identifikation><ns0:name>Nachname</ns0:name>"
        "<ns0:bezeichnungEingabe>Nachname</ns0:bezeichnungEingabe>"
        "<ns0:bezeichnungAusgabe>Nachname</ns0:bezeichnungAusgabe>"
        "<ns0:status listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.status\" listVersionID=\"1.0\">"
        "<code>aktiv</code></ns0:status>"
        "<ns0:schemaelementart listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.schemaelementart\" "
        "listVersionID=\"1.0\"><code>HAR</code></ns0:schemaelementart>"
        "<ns0:feldart listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.feldart\" listVersionID=\"1.0\">"
        "<code>input</code></ns0:feldart>"
        "<ns0:datentyp listURI=\"urn:xoev-de:fim:codeliste:xdatenfelder.datentyp\" listVersionID=\"1.0\">"
        "<code>text</code></ns0:datentyp></ns0:datenfeld></ns0:enthaelt></ns0:struktur>"
        "</ns0:stammdatenschema></ns0:xdatenfelder.stammdatenschema.0102>"
    )
    xsd = client.convert_xdf2_to_xsd(minimal_xdf)
    assert "xs:schema" in xsd
