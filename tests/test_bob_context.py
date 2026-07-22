"""Live-Test gegen die echte FIM-Portal-API.

Validiert das konkrete, recherchierte Beispiel: LeiKa 99003002022000
("Belehrung nach dem Infektionsschutzgesetz Bescheinigung") muss über die
Rechtsgrundlage "§ 43 Absatz 1 Infektionsschutzgesetz (IfSG)" das echte
Referenzschema S00000253 finden und dessen BOB-Bausteine (Nummernkreis 60000)
liefern.
"""
import pytest

from ai_mapper.bob_context import _nummernkreis_von_id, harvest_bob_bausteine, resolve_leika_kontext
from ai_mapper.fim_client import FimClient

LEIKA_INFEKTIONSSCHUTZ = "99003002022000"


def test_nummernkreis_extraktion():
    assert _nummernkreis_von_id("F60000227") == "60000"
    assert _nummernkreis_von_id("F60000000227") == "60000"
    assert _nummernkreis_von_id("F00000013") == "00000"


def test_resolve_leika_kontext_findet_referenzschema():
    client = FimClient()
    kontext = resolve_leika_kontext(LEIKA_INFEKTIONSSCHUTZ, client)

    assert "Infektionsschutz" in (kontext.leistungsbezeichnung or "")
    assert kontext.rechtsgrundlagen
    assert "S00000253/1.0" in kontext.aehnliche_schemas


def test_harvest_bob_bausteine_liefert_kandidaten():
    client = FimClient()
    kontext = resolve_leika_kontext(LEIKA_INFEKTIONSSCHUTZ, client)
    kandidaten = harvest_bob_bausteine(kontext, client)

    assert len(kandidaten) > 0
    assert all(k.aus_domain_kontext for k in kandidaten)
    assert all(k.fim_id.startswith("F6") for k in kandidaten)


def test_resolve_leika_kontext_unbekannte_nummer():
    client = FimClient()
    kontext = resolve_leika_kontext("00000000000000", client)
    assert kontext.leistungsbezeichnung is None
    assert kontext.aehnliche_schemas == []
