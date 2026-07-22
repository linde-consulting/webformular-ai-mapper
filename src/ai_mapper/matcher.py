"""Matching einzelner Formularfelder gegen FIM-Portal-Kandidaten.

Nutzt Claude (Anthropic API) zur semantischen Entscheidung REUSE/NEU, wenn
ANTHROPIC_API_KEY gesetzt ist. Ohne Key: regelbasierter Fallback über
String-Ähnlichkeit (difflib), damit die Pipeline auch ohne LLM lauffähig bleibt.
"""
from __future__ import annotations

import difflib
import json
import os
from typing import List, Optional

from .models import FimKandidat, Formularfeld
from .schema_builder import DATENTYP_MAPPING

FALLBACK_SCHWELLENWERT = 0.72

# Bonus für Kandidaten aus dem LeiKa-Domain-Kontext (bereits in einem Schema mit
# gleicher Rechtsgrundlage verwendete BOB-Bausteine) - sorgt bei Gleichstand dafür,
# dass der fachlich passende Baustein statt eines generischen Treffers gewinnt.
DOMAIN_KONTEXT_BONUS = 0.08


def _normalisiere(text: str) -> str:
    return text.strip().lower()


def _aehnlichkeit(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalisiere(a), _normalisiere(b)).ratio()


def regelbasiertes_matching(feld: Formularfeld, kandidaten: List[FimKandidat]):
    """Wählt den ähnlichsten Kandidaten über einem Schwellenwert, sonst NEU.

    Reine Wortlaut-Ähnlichkeit kann Begriffe mit gemeinsamem Wortstamm aber
    unterschiedlicher Bedeutung verwechseln (z. B. "Geburtsdatum" vs.
    "Geburtsname" - Score 0.86 trotz komplett anderen Inhalts). Deshalb werden
    Kandidaten mit bekanntem, inkompatiblem Datentyp ausgeschlossen.
    """
    erwarteter_datentyp = DATENTYP_MAPPING[feld.typ][0]

    bester: Optional[FimKandidat] = None
    beste_score = 0.0
    for k in kandidaten:
        if k.datentyp and k.datentyp != erwarteter_datentyp:
            continue
        score = _aehnlichkeit(feld.label, k.name)
        if k.aus_domain_kontext:
            score = min(1.0, score + DOMAIN_KONTEXT_BONUS)
        if score > beste_score:
            beste_score = score
            bester = k

    if bester is not None and beste_score >= FALLBACK_SCHWELLENWERT:
        return bester, beste_score, (
            f"Regelbasierter Fallback: Label '{feld.label}' ähnelt FIM-Datenfeld "
            f"'{bester.name}' ({bester.namespace}/{bester.fim_id}/{bester.fim_version}) "
            f"mit Score {beste_score:.2f} (Schwelle {FALLBACK_SCHWELLENWERT})."
        )
    return None, beste_score, (
        f"Regelbasierter Fallback: kein Kandidat über Schwellenwert {FALLBACK_SCHWELLENWERT} "
        f"gefunden (bester Score {beste_score:.2f}) -> neues Datenfeld wird angelegt."
    )


def claude_matching(feld: Formularfeld, kandidaten: List[FimKandidat], model: str):
    """Lässt Claude über Anthropic-API die Wiederverwendung entscheiden."""
    import anthropic

    client = anthropic.Anthropic()

    erwarteter_datentyp = DATENTYP_MAPPING[feld.typ][0]

    kandidaten_liste = "\n".join(
        f"- index={i} | namespace={k.namespace} | fim_id={k.fim_id} | version={k.fim_version} | "
        f"name='{k.name}' | definition='{(k.definition or '')[:200]}' | "
        f"freigabe_status={k.freigabe_status} | datentyp={k.datentyp} | "
        f"domain_kontext={'JA - bereits in einem Schema mit gleicher Rechtsgrundlage/Leistung verwendet' if k.aus_domain_kontext else 'nein - generischer Volltext-Treffer'}"
        for i, k in enumerate(kandidaten)
    ) or "(keine Kandidaten gefunden)"

    prompt = f"""Du hilfst dabei, ein FIM-XDatenfelder-Referenzschema für ein Webformular zu bauen.
Für das Formularfeld unten sollen bestehende FIM-Datenfelder wiederverwendet werden, wenn sie
fachlich wirklich passen (gleiche Bedeutung, nicht nur ähnlicher Wortlaut). Sonst muss ein neues
Datenfeld angelegt werden. Kandidaten mit domain_kontext=JA stammen aus einem bereits für eine
sehr ähnliche Verwaltungsleistung (gleiche Rechtsgrundlage) genutzten Referenzschema und sind bei
fachlicher Eignung zu bevorzugen, da sie den etablierten BOB-Baustein für diesen Anwendungsfall
darstellen.

Formularfeld:
- label: {feld.label}
- typ: {feld.typ} (erwarteter FIM-Datentyp: {erwarteter_datentyp})
- pflichtfeld: {feld.pflichtfeld}
- hilfetext: {feld.hilfetext or "-"}

Ein Kandidat mit abweichendem Datentyp passt fast nie (z. B. "Geburtsdatum" und
"Geburtsname" klingen ähnlich, sind aber inhaltlich verschieden) - im Zweifel
NEU wählen statt einen falschen Datentyp wiederzuverwenden.

Kandidaten aus dem FIM-Portal (Volltextsuche nach dem Label):
{kandidaten_liste}

Antworte NUR mit JSON in diesem Format, ohne weiteren Text:
{{"entscheidung": "REUSE" oder "NEU", "kandidat_index": <int oder null>, "confidence": <0.0-1.0>, "begruendung": "<kurzer Satz auf Deutsch>"}}
"""

    resp = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if text.lower().startswith("json") else text
    data = json.loads(text)

    if data["entscheidung"] == "REUSE" and data.get("kandidat_index") is not None:
        idx = int(data["kandidat_index"])
        if 0 <= idx < len(kandidaten):
            return kandidaten[idx], float(data.get("confidence", 0.8)), data.get("begruendung", "")
    return None, float(data.get("confidence", 0.5)), data.get("begruendung", "Claude: neues Datenfeld erforderlich.")


def match_feld(feld: Formularfeld, kandidaten: List[FimKandidat]):
    """Einstiegspunkt: Claude wenn ANTHROPIC_API_KEY gesetzt ist, sonst Fallback.

    Rückgabe: (kandidat_oder_None, confidence, begruendung)
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        model = os.environ.get("AI_MAPPER_MODEL", "claude-sonnet-4-5")
        try:
            return claude_matching(feld, kandidaten, model)
        except Exception as exc:  # Fallback bei API-/Parsing-Fehlern, Pipeline soll nicht abbrechen
            kandidat, score, begr = regelbasiertes_matching(feld, kandidaten)
            return kandidat, score, f"[Claude-Matching fehlgeschlagen: {exc}] {begr}"
    return regelbasiertes_matching(feld, kandidaten)
