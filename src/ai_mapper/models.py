from typing import List, Optional, Literal

from pydantic import BaseModel, Field

FeldTyp = Literal[
    "text", "mehrzeilig", "email", "tel", "zahl", "ganzzahl",
    "betrag", "datum", "auswahl", "checkbox", "datei",
]


class Formularfeld(BaseModel):
    id: str
    label: str
    typ: FeldTyp
    pflichtfeld: bool = False
    optionen: Optional[List[str]] = None
    abschnitt: Optional[str] = None
    hilfetext: Optional[str] = None
    # Technischer Name im Ursprungssystem (z. B. FORMCYCLE-Feldname wie
    # "tf1_st_Vorname") - unverändert, nicht slugifiziert. Wird für die
    # %-Variablen-Bindung im FORMCYCLE-Export gebraucht. Fällt auf `id` zurück,
    # wenn das Ursprungssystem keinen eigenen technischen Namen liefert (z. B. CSV/XLSX).
    technischer_name: Optional[str] = None


class FormularInput(BaseModel):
    titel: str
    leika_nummer: Optional[str] = None
    felder: List[Formularfeld]


class FimKandidat(BaseModel):
    namespace: str
    fim_id: str
    fim_version: str
    name: str
    definition: Optional[str] = None
    freigabe_status: Optional[int] = None
    feldart: Optional[str] = None
    datentyp: Optional[str] = None
    aus_domain_kontext: bool = False
    # Datenfeldgruppe, in der dieses Datenfeld im Ursprungsschema eingebettet war
    # (nur bekannt für über harvest_bob_bausteine geerntete Domain-Kontext-Kandidaten).
    gruppe_id: Optional[str] = None
    gruppe_version: Optional[str] = None


class LeikaKontext(BaseModel):
    leika_nummer: str
    leistungsbezeichnung: Optional[str] = None
    rechtsgrundlagen: Optional[str] = None
    ozg_themenfeld: Optional[str] = None
    aehnliche_schemas: List[str] = []


class MatchErgebnis(BaseModel):
    feld_id: str
    label: str
    status: Literal["REUSE", "NEU"]
    confidence: float
    begruendung: str
    fim_kandidat: Optional[FimKandidat] = None
    neue_id: Optional[str] = None
    datenfeld_xml: str = Field(exclude=True, default="")


class MappingReport(BaseModel):
    schema_id: str
    schema_version: str
    titel: str
    leika_nummer: Optional[str] = None
    leika_kontext: Optional[LeikaKontext] = None
    matches: List[MatchErgebnis]
