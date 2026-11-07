#!/usr/bin/env python3
"""Importación controlada de ratings EA SPORTS FC desde un CSV autorizado.

No descarga de EA ni hace scraping. No une jugadores por nombre de forma
automática; es obligatorio tener un mapeo de identificadores revisado.
Los archivos generados son locales y están excluidos de Git.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import re

FIELDS = (
    "edition", "as_of_date", "fc_player_id", "name", "club", "position",
    "ovr", "pac", "sho", "pas", "dri", "def", "phy", "source_url",
)
RATING_FIELDS = ("ovr", "pac", "sho", "pas", "dri", "def", "phy")


def validate(rows: list[dict]) -> list[dict]:
    if not rows:
        raise ValueError("No hay jugadores en el archivo")
    seen = set()
    out = []
    for number, row in enumerate(rows, 2):
        missing = set(FIELDS) - set(row)
        if missing:
            raise ValueError(f"Línea {number}: faltan columnas {sorted(missing)}")
        edition = str(row["edition"]).strip()
        if not re.fullmatch(r"FC(2[5-9]|[3-9][0-9])", edition):
            raise ValueError(f"Línea {number}: edición no válida: {edition}")
        try:
            date.fromisoformat(str(row["as_of_date"]))
        except ValueError as exc:
            raise ValueError(f"Línea {number}: fecha inválida") from exc
        player_id = str(row["fc_player_id"]).strip()
        if not player_id or not player_id.isdecimal():
            raise ValueError(f"Línea {number}: fc_player_id no válido")
        key = (edition, str(row["as_of_date"]), player_id)
        if key in seen:
            raise ValueError(f"Línea {number}: jugador duplicado por edición y snapshot")
        seen.add(key)
        for field in ("name", "club", "position"):
            if not str(row[field]).strip():
                raise ValueError(f"Línea {number}: {field} vacío")
        source = str(row["source_url"]).strip()
        if not source.startswith("https://"):
            raise ValueError(f"Línea {number}: source_url debe ser HTTPS")
        for field in RATING_FIELDS:
            value = str(row[field]).strip()
            if value:
                if not value.isdecimal() or not 0 <= int(value) <= 99:
                    raise ValueError(f"Línea {number}: {field} fuera de 0..99")
            elif field == "ovr":
                raise ValueError(f"Línea {number}: ovr obligatorio")
        out.append({field: str(row[field]).strip() for field in FIELDS})
    return out


def import_ratings(input_path: Path, output_path: Path) -> dict:
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = validate(list(reader))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "records": len(rows),
        "editions": sorted(set(r["edition"] for r in rows)),
        "snapshot_dates": sorted(set(r["as_of_date"] for r in rows)),
        "status": "imported_not_verified_against_ea",
        "note": "Importado de un CSV aportado bajo licencia. No implica autorización de redistribución, ni cifras verificadas por EA.",
        "identity_matching": "pending_reviewed_id_mapping",
    }
    (output_path.parent / "ratings_import_status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validar datos de EA FC legalmente obtenidos")
    parser.add_argument("input", type=Path, help="CSV de ratings con derechos de uso")
    parser.add_argument("--out", type=Path, default=Path("datasets/ratings/fc_ratings.csv"))
    args = parser.parse_args()
    print(json.dumps(import_ratings(args.input, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
