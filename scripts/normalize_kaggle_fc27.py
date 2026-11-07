#!/usr/bin/env python3
"""Normalizar el CSV FC27 de Kaggle a la tabla local de ratings.

La salida se crea solo en un directorio excluido de Git; no verifica
licencia ni equivalencias de identidades con fuentes deportivas.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path

from scripts.audit_kaggle_fc27 import DATASET, DATASET_URL, schema_map, validate_rating
from scripts.import_fc_ratings import FIELDS, import_ratings


def normalize_csv(source_file: Path, destination: Path) -> dict:
    with source_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        mapping = schema_map(columns)
        required = ("fc_player_id", "ovr", "club", "position")
        missing = [key for key in required if not mapping[key]]
        if missing:
            raise ValueError("El dataset no contiene campos necesarios: " + ", ".join(missing))
        lowered = {x.lower(): x for x in columns}
        date_col = lowered.get("snapshot_date")
        edition_col = lowered.get("edition")
        first_col = lowered.get("first_name")
        last_col = lowered.get("last_name")
        if not date_col:
            raise ValueError("Fecha snapshot_date no disponible en CSV: no asignar una fecha inventada")
        rows = []
        for line, row in enumerate(reader, 2):
            edition = str(row.get(edition_col) or "FC27").strip().upper()
            if edition != "FC27":
                raise ValueError(f"Fila {line}: edición inesperada {edition}")
            as_of_date = str(row.get(date_col) or "").strip()
            try:
                date.fromisoformat(as_of_date)
            except ValueError as exc:
                raise ValueError(f"Fila {line}: snapshot_date inválida") from exc
            name = (str(row.get(mapping["name"]) or "").strip() if mapping["name"] else "")
            if not name:
                name = " ".join(x.strip() for x in [
                    str(row.get(first_col) or ""), str(row.get(last_col) or "")
                ] if x.strip())
            record = {
                "edition": edition,
                "as_of_date": as_of_date,
                "fc_player_id": str(row.get(mapping["fc_player_id"]) or "").strip(),
                "name": name,
                "club": str(row.get(mapping["club"]) or "").strip(),
                "position": str(row.get(mapping["position"]) or "").strip(),
                "source_url": DATASET_URL,
            }
            for metric in ("ovr", "pac", "sho", "pas", "dri", "def", "phy"):
                col = mapping[metric]
                value = validate_rating(row.get(col), metric, line) if col else None
                record[metric] = "" if value is None else str(value)
            rows.append(record)
    # Invoca la validación estricta existente ANTES de declarar éxito.
    destination.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        intermediate = Path(tmp) / "fc27_normalizado.csv"
        with intermediate.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        import_ratings(intermediate, destination)
    # El status no debe declarar autenticidad o derechos de reutilización.
    status = {
        "source": DATASET_URL,
        "records": len(rows),
        "status": "normalized_locally_pending_rights_and_identity_mapping",
        "copyright_license_cleared": False,
        "joined_to_match_players": False,
        "destination": str(destination),
    }
    (destination.parent / "kaggle_fc27_import.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalizar ratings FC27 Kaggle localmente")
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("datasets/ratings/fc_ratings.csv"))
    args = parser.parse_args()
    if args.local_dir:
        folder = args.local_dir
    else:
        try:
            import kagglehub
        except ImportError as exc:
            raise SystemExit("Instala kagglehub antes de descargar") from exc
        folder = Path(kagglehub.dataset_download(DATASET))
    inputs = list(folder.rglob("players.csv"))
    if len(inputs) != 1:
        raise ValueError(f"Se esperaba un único archivo players.csv; encontrados: {len(inputs)}")
    result = normalize_csv(inputs[0], args.out)
    print(json.dumps({
        "source": DATASET_URL,
        "normalized_player_rows": result["records"],
        "license_cleared": False,
        "joined_to_match_players": False,
        "file_local_only": str(args.out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
