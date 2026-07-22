import json

from ai_mapper.formcycle_export import build_formcycle_template
from ai_mapper.models import FimKandidat, Formularfeld, MatchErgebnis


def test_reuse_feld_wird_seiner_gruppe_zugeordnet_und_variable_gebunden():
    feld = Formularfeld(id="vorname", label="Vorname", typ="text", technischer_name="tf1_st_Vorname")
    kandidat = FimKandidat(
        namespace="baukasten",
        fim_id="F60000228",
        fim_version="2.0",
        name="Vornamen",
        gruppe_id="G00002115",
        gruppe_version="1.0",
        aus_domain_kontext=True,
    )
    match = MatchErgebnis(
        feld_id="vorname", label="Vorname", status="REUSE", confidence=1.0,
        begruendung="test", fim_kandidat=kandidat,
    )

    ergebnis = json.loads(
        build_formcycle_template("S1", "1.0", "Testformular", [feld], [match], leika_nummer="123")
    )

    assert len(ergebnis["gruppenInitialisierung"]) == 1
    gruppe = ergebnis["gruppenInitialisierung"][0]
    assert gruppe["fimGruppeId"] == "G00002115"
    assert gruppe["felder"][0]["fimFeldId"] == "F60000228"
    assert gruppe["felder"][0]["formcycleVariable"] == "%tf1_st_Vorname%"
    assert ergebnis["ungruppierteFelder"] == []


def test_neues_feld_ohne_gruppe_landet_in_ungruppierten_feldern():
    feld = Formularfeld(id="sonderfeld", label="Sonderfeld", typ="text")
    match = MatchErgebnis(
        feld_id="sonderfeld", label="Sonderfeld", status="NEU", confidence=0.0,
        begruendung="test", neue_id="F99999999",
    )

    ergebnis = json.loads(
        build_formcycle_template("S1", "1.0", "Testformular", [feld], [match])
    )

    assert ergebnis["gruppenInitialisierung"] == []
    assert ergebnis["ungruppierteFelder"][0]["fimFeldId"] == "F99999999"
    # ohne technischer_name fällt die %-Variable auf die interne id zurück
    assert ergebnis["ungruppierteFelder"][0]["formcycleVariable"] == "%sonderfeld%"


def test_zwei_felder_gleicher_gruppe_werden_zusammengefasst():
    felder = [
        Formularfeld(id="vorname", label="Vorname", typ="text", technischer_name="tf_vorname"),
        Formularfeld(id="nachname", label="Nachname", typ="text", technischer_name="tf_nachname"),
    ]
    kandidat_gemeinsame_gruppe = dict(gruppe_id="G1", gruppe_version="1.0", aus_domain_kontext=True, namespace="baukasten")
    matches = [
        MatchErgebnis(feld_id="vorname", label="Vorname", status="REUSE", confidence=1.0, begruendung="",
                      fim_kandidat=FimKandidat(fim_id="F1", fim_version="1.0", name="Vorname", **kandidat_gemeinsame_gruppe)),
        MatchErgebnis(feld_id="nachname", label="Nachname", status="REUSE", confidence=1.0, begruendung="",
                      fim_kandidat=FimKandidat(fim_id="F2", fim_version="1.0", name="Nachname", **kandidat_gemeinsame_gruppe)),
    ]

    ergebnis = json.loads(
        build_formcycle_template("S1", "1.0", "Testformular", felder, matches)
    )

    assert len(ergebnis["gruppenInitialisierung"]) == 1
    assert len(ergebnis["gruppenInitialisierung"][0]["felder"]) == 2
