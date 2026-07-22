"""CLI - läuft eigenständig, ohne Claude/Claude-Code:

python -m ai_mapper.cli map --input formular.json --output out/
python -m ai_mapper.cli map --input formular.csv --titel "Mein Formular" \\
    --leika-nummer 99003002022000 --output out/
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .fim_client import FimClient
from .formular_import import build_formular_input
from .pipeline import render_mapping_report_markdown, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-mapper")
    sub = parser.add_subparsers(dest="command", required=True)

    map_parser = sub.add_parser("map", help="Formular in Referenzschema + Formcycle-Template mappen")
    map_parser.add_argument("--input", required=True, help="Pfad zur Formular-Datei (.json, .csv oder .xlsx)")
    map_parser.add_argument("--output", required=True, help="Zielordner für die Ergebnisdateien")
    map_parser.add_argument("--titel", default=None, help="Formular-Titel (nur bei .csv/.xlsx nötig)")
    map_parser.add_argument(
        "--leika-nummer", default=None, help="LeiKa-Nummer (optional, aktiviert BOB-Domain-Matching)"
    )
    map_parser.add_argument(
        "--fim-base-url", default=os.environ.get("FIM_API_BASE", "https://fimportal.de")
    )

    args = parser.parse_args()

    if args.command == "map":
        run_map(args.input, args.output, args.titel, args.leika_nummer, args.fim_base_url)


def run_map(input_path: str, output_dir: str, titel, leika_nummer, fim_base_url: str) -> None:
    pfad = Path(input_path)
    formular = build_formular_input(pfad.read_bytes(), pfad.name, titel, leika_nummer)
    client = FimClient(base_url=fim_base_url)

    ergebnis = run_pipeline(formular, client)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "schema.xdf.xml").write_text(ergebnis.xdf_xml, encoding="utf-8")
    (out / "schema.xsd").write_text(ergebnis.xsd_xml, encoding="utf-8")
    (out / "formcycle-plugin-mapping.json").write_text(ergebnis.formcycle_json, encoding="utf-8")
    (out / "mapping-report.md").write_text(render_mapping_report_markdown(ergebnis), encoding="utf-8")

    print(f"Fertig. Ergebnisse in: {out.resolve()}")
    for m in ergebnis.report.matches:
        print(f"  - {m.label}: {m.status} (confidence {m.confidence:.2f})")


if __name__ == "__main__":
    main()
