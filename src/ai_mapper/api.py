"""Minimale FastAPI-App: Formular hochladen, Ergebnis als ZIP herunterladen.

Läuft komplett eigenständig (Docker, kein Claude/Claude-Code-Zugang nötig).
Akzeptiert wahlweise eine vollständige Formular-JSON oder eine einfache
CSV/XLSX-Feldtabelle (siehe formular_import.py und examples/formular-vorlage.csv).
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from .fim_client import FimClient
from .formular_import import FormularImportError, build_formular_input
from .pipeline import render_mapping_report_markdown, run_pipeline

app = FastAPI(title="FIT-Connect AI-Mapper")

VORLAGE_PFAD = Path(__file__).parent.parent.parent / "examples" / "formular-vorlage.csv"


@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    return """
    <!doctype html>
    <html lang="de">
    <head><meta charset="utf-8"><title>FIT-Connect AI-Mapper</title></head>
    <body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
      <h1>FIT-Connect AI-Mapper</h1>
      <p>Formular hochladen, um ein FIM-Referenzschema (XSD) und ein
      FORMCYCLE-Plugin-Template zu erzeugen.</p>
      <p>Zwei Möglichkeiten:</p>
      <ul>
        <li>Ein echter <strong>FORMCYCLE-Export</strong> (Menü "Formular exportieren", JSON) -
        wird automatisch erkannt, LeiKa-Nummer unten ergänzen</li>
        <li>Eine <strong>CSV- oder XLSX-Feldtabelle</strong> (Titel + LeiKa-Nummer
        unten ausfüllen) - <a href="/vorlage">Vorlage herunterladen</a></li>
        <li>Eine vollständige <strong>Formular-JSON</strong> im eigenen Format (Titel/LeiKa bereits enthalten)</li>
      </ul>
      <form action="/map" method="post" enctype="multipart/form-data">
        <p><label>Titel (nur bei CSV/XLSX nötig):<br>
          <input type="text" name="titel" style="width:100%"></label></p>
        <p><label>LeiKa-Nummer (optional, aktiviert BOB-Domain-Matching):<br>
          <input type="text" name="leika_nummer" style="width:100%"></label></p>
        <p><input type="file" name="datei" accept=".json,.csv,.xlsx" required></p>
        <button type="submit">Mapping starten</button>
      </form>
    </body>
    </html>
    """


@app.get("/vorlage")
def vorlage_herunterladen() -> FileResponse:
    return FileResponse(VORLAGE_PFAD, media_type="text/csv", filename="formular-vorlage.csv")


@app.post("/map")
async def map_formular(
    datei: UploadFile = File(...),
    titel: str = Form(""),
    leika_nummer: str = Form(""),
) -> StreamingResponse:
    try:
        inhalt = await datei.read()
        formular = build_formular_input(
            inhalt, datei.filename or "", titel or None, leika_nummer or None
        )
    except FormularImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ungültige Eingabedatei: {exc}")

    client = FimClient(base_url=os.environ.get("FIM_API_BASE", "https://fimportal.de"))
    ergebnis = run_pipeline(formular, client)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("schema.xdf.xml", ergebnis.xdf_xml)
        zf.writestr("schema.xsd", ergebnis.xsd_xml)
        zf.writestr("formcycle-plugin-mapping.json", ergebnis.formcycle_json)
        zf.writestr("mapping-report.md", render_mapping_report_markdown(ergebnis))
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={ergebnis.report.schema_id}.zip"},
    )
