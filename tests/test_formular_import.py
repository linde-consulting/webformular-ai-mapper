import pytest

from ai_mapper.formular_import import FormularImportError, parse_feld_datei

BEISPIEL_CSV = (
    "Abschnitt,Feld-ID,Label,Typ,Pflichtfeld,Optionen,Hilfetext\n"
    "Person,nachname,Nachname,text,ja,,\n"
    "Person,,Vorname,text,nein,,\n"
).encode("utf-8")


def test_parse_csv_liest_alle_felder():
    felder = parse_feld_datei(BEISPIEL_CSV, "test.csv")
    assert len(felder) == 2
    assert felder[0].id == "nachname"
    assert felder[0].label == "Nachname"
    assert felder[0].typ == "text"
    assert felder[0].pflichtfeld is True
    assert felder[0].abschnitt == "Person"


def test_parse_csv_generiert_id_aus_label_wenn_leer():
    felder = parse_feld_datei(BEISPIEL_CSV, "test.csv")
    assert felder[1].id == "vorname"
    assert felder[1].pflichtfeld is False


def test_parse_csv_fehlt_pflichtspalte():
    csv_ohne_typ = "Label\nNachname\n".encode("utf-8")
    with pytest.raises(FormularImportError, match="Pflichtspalten"):
        parse_feld_datei(csv_ohne_typ, "test.csv")


def test_parse_csv_ungueltiger_typ():
    csv_falscher_typ = "Label,Typ\nNachname,ungueltig\n".encode("utf-8")
    with pytest.raises(FormularImportError, match="Ungültiger Typ"):
        parse_feld_datei(csv_falscher_typ, "test.csv")


def test_parse_csv_dedupliziert_ids():
    csv_gleiche_labels = (
        "Label,Typ\nName,text\nName,text\n"
    ).encode("utf-8")
    felder = parse_feld_datei(csv_gleiche_labels, "test.csv")
    ids = [f.id for f in felder]
    assert len(ids) == len(set(ids))


def test_parse_datei_nicht_unterstuetztes_format():
    with pytest.raises(FormularImportError, match="Nicht unterstütztes"):
        parse_feld_datei(b"irrelevant", "formular.txt")
