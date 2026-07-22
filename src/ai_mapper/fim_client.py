"""Client für die öffentliche FIM-Portal-REST-API (fimportal.de).

Verifiziert gegen die echte API am 2026-07-14:
- GET  /api/v1/fields / /api/v1/groups / /api/v1/schemas  (Volltextsuche, Parameter `fts_query`)
- GET  /api/v1/fields/{namespace}/{fim_id}/{fim_version}/xdf  (XDatenfelder-2.0-XML-Export)
- POST /tools/xdf2-xsd-converter  (multipart, Feldname `schema`) -> XSD als application/xml
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List, Optional

import requests

from .models import FimKandidat

XDF2_NS = "urn:xoev-de:fim:standard:xdatenfelder_2"
# "ns0" ist als Präfix-Format bei ElementTree reserviert (ns\d+) -> eigenes Präfix verwenden.
ET.register_namespace("xdf", XDF2_NS)

DEFAULT_BASE_URL = "https://fimportal.de"

# Nur fachlich freigegebene ("gold", Status 6) Elemente wiederverwenden.
FREIGABE_STATUS_GOLD = 6


class FimClientError(RuntimeError):
    pass


class FimClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()

    def _get(self, path: str, params: dict) -> dict:
        resp = self._session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise FimClientError(f"GET {path} fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
        return resp.json()

    def _search(self, path: str, query: str, xdf_version: str = "2.0", limit: int = 10) -> List[dict]:
        data = self._get(
            path,
            params={
                "fts_query": query,
                "freigabe_status": [FREIGABE_STATUS_GOLD],
                "xdf_version": xdf_version,
            },
        )
        return data.get("items", [])[:limit]

    def search_fields(self, query: str, limit: int = 10) -> List[FimKandidat]:
        items = self._search("/api/v1/fields", query, limit=limit)
        return [
            FimKandidat(
                namespace=it["namespace"],
                fim_id=it["fim_id"],
                fim_version=it["fim_version"],
                name=it["name"],
                definition=it.get("definition"),
                freigabe_status=it.get("freigabe_status"),
                feldart=it.get("feldart"),
                datentyp=it.get("datentyp"),
            )
            for it in items
        ]

    def search_groups(self, query: str, limit: int = 5) -> List[dict]:
        return self._search("/api/v1/groups", query, limit=limit)

    def search_schemas(self, query: str, limit: int = 5) -> List[dict]:
        return self._search("/api/v1/schemas", query, limit=limit)

    def get_leistung(self, leika_nummer: str) -> Optional[dict]:
        """Lädt die LeiKa-Leistungsbeschreibung (Rechtsgrundlage, OZG-Themenfeld etc.)."""
        data = self._get(
            "/api/v1/leistung-steckbriefe",
            params={"leistungsschluessel": leika_nummer, "limit": 1},
        )
        items = data.get("items", [])
        return items[0] if items else None

    def get_schema_xdf_root(self, fim_id: str, fim_version: str) -> ET.Element:
        """Lädt den vollständigen XDF2-Export eines Referenzschemas (Wurzelelement)."""
        url = f"{self.base_url}/api/v1/schemas/{fim_id}/{fim_version}/xdf"
        resp = self._session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise FimClientError(f"Schema-Export fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
        return ET.fromstring(resp.content)

    def get_field_datenfeld_xml(self, namespace: str, fim_id: str, fim_version: str) -> ET.Element:
        """Lädt den XDF2-Export eines Datenfelds und gibt das <datenfeld>-Element zurück."""
        url = f"{self.base_url}/api/v1/fields/{namespace}/{fim_id}/{fim_version}/xdf"
        resp = self._session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise FimClientError(f"Feld-Export fehlgeschlagen ({resp.status_code}): {resp.text[:300]}")
        root = ET.fromstring(resp.content)
        elem = root.find(f"{{{XDF2_NS}}}datenfeld")
        if elem is None:
            raise FimClientError(f"Kein <datenfeld> im Export von {namespace}/{fim_id}/{fim_version} gefunden")
        return elem

    def convert_xdf2_to_xsd(self, xdf2_xml: str, code_lists: Optional[List[bytes]] = None) -> str:
        files = [("schema", ("schema.xml", xdf2_xml.encode("utf-8"), "application/xml"))]
        for i, cl in enumerate(code_lists or []):
            files.append(("code_lists", (f"codeliste_{i}.xml", cl, "application/xml")))
        resp = self._session.post(
            f"{self.base_url}/tools/xdf2-xsd-converter", files=files, timeout=self.timeout
        )
        if resp.status_code != 200:
            raise FimClientError(f"XSD-Konvertierung fehlgeschlagen ({resp.status_code}): {resp.text[:500]}")
        return resp.text
