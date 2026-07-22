import json
from pathlib import Path

from ai_mapper.fim_client import FimClient
from ai_mapper.models import FormularInput
from ai_mapper.pipeline import render_mapping_report_markdown, run_pipeline

EXAMPLE_PATH = Path(__file__).parent.parent / "examples" / "beispiel-formular.json"


def test_end_to_end_mit_beispielformular():
    daten = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    formular = FormularInput.model_validate(daten)
    client = FimClient()

    ergebnis = run_pipeline(formular, client)

    assert ergebnis.report.schema_id.startswith("S9")
    assert "xs:schema" in ergebnis.xsd_xml

    formcycle_daten = json.loads(ergebnis.formcycle_json)
    assert "fachdatenSchema" in formcycle_daten
    assert "gruppenInitialisierung" in formcycle_daten
    assert "ungruppierteFelder" in formcycle_daten
    assert len(ergebnis.report.matches) == len(formular.felder)

    report_md = render_mapping_report_markdown(ergebnis)
    assert "Mapping-Report" in report_md
