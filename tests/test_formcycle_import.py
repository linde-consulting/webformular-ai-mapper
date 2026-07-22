import json
from pathlib import Path

from ai_mapper.formcycle_import import (
    formular_titel,
    ist_formcycle_export,
    parse_formcycle_export,
)
from ai_mapper.formular_import import build_formular_input

ECHTER_EXPORT_PFAD = Path(__file__).parent.parent / "examples" / "webform-Neues Formular.json"


def _lade_echten_export() -> dict:
    return json.loads(ECHTER_EXPORT_PFAD.read_text(encoding="utf-8"))


def test_ist_formcycle_export_erkennt_echten_export():
    daten = _lade_echten_export()
    assert ist_formcycle_export(daten) is True


def test_ist_formcycle_export_erkennt_eigenes_format_nicht_als_formcycle():
    assert ist_formcycle_export({"titel": "x", "felder": []}) is False


def test_formular_titel_aus_echtem_export():
    daten = _lade_echten_export()
    assert formular_titel(daten) == "Neues Formular"


def test_parse_formcycle_export_extrahiert_nur_echte_felder():
    daten = _lade_echten_export()
    felder = parse_formcycle_export(daten)

    labels = [f.label for f in felder]
    assert labels == ["Vorname", "Nachname", "Strasse"]
    assert all(f.typ == "text" for f in felder)
    # Layout-/Deko-Elemente (Header, Page, Footer) dürfen nicht als Felder auftauchen
    assert not any("footer" in f.id or "header" in f.id for f in felder)


def test_build_formular_input_dispatcht_formcycle_export():
    inhalt = ECHTER_EXPORT_PFAD.read_bytes()
    formular = build_formular_input(inhalt, "webform-Neues Formular.json")

    assert formular.titel == "Neues Formular"
    assert len(formular.felder) == 3
