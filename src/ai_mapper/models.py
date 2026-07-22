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
