#!/usr/bin/env python3
"""Audita el dataset comunitario de EA FC 27 en Kaggle.

No extrae datos de ea.com. No publica jugadores ni ratings en GitHub.
Las valoraciones son una fotografía del videojuego, NO estadísticas reales.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

DATASET = "mikedpad/ea-sports-fc27-player-ratings"
DATASET_URL = f"https://www.kaggle.com/datasets/{DATASET}"
CORE_ALIASES = {
    "fc_player_id": ("player_id", "id", "playerid", "ea_id", "sofifa_id", "fifa_id"),
    "name": ("name", "player_name", "full_name", "display_name", "short_name", "common_name"),
    "club": ("club", "team", "team_name", "club_name"),
    "position": ("position", "preferred_position", "player_position"),
    "ovr": ("overall_rating", "overall", "ovr", "rating", "overallrating"),
    "pac": ("pac", "pace"),
    "sho": ("sho", "shooting"),
    "pas": ("pas", "passing"),
    "dri": ("dri", "dribbling"),
    "def": ("def", "defending"),
    "phy": ("phy", "physicality", "physical"),
}
DETAIL_ALIASES = (
    "attacking_finishing", "attacking_positioning", "power_shot_power",
    "power_long_shots", "mentality_penalties", "weak_foot",
    "skill_moves", "movement_acceleration", "movement_sprint_speed",
    "goalkeeping_diving", "goalkeeping_handling", "goalkeeping_reflexes",
)


def normalize_column(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def schema_map(columns: list[str]) -> dict[str, str]:
    by_normalized = {normalize_column(x): x for x in columns}
    return {
        canonical: next((by_normalized[x] for x in aliases
                         if x in by_normalized), "")
        for canonical, aliases in CORE_ALIASES.items()
    }


def validate_rating(value: str, kind: str, line: int) -> int | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if not cleaned.isdecimal() or not 0 <= int(cleaned) <= 99:
        raise ValueError(f"Fila {line}: {kind} fuera de 0..99")
    return int(cleaned)


def inspect_csv(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError(f"Archivo CSV sin cabecera: {path.name}")
        mapped = schema_map(headers)
        if not mapped["ovr"]:
            raise ValueError(f"{path.name}: no hay campo Overall/OVR reconocido")
        if not mapped["fc_player_id"]:
            raise ValueError(f"{path.name}: no hay ID de jugador reconocido")
        if not mapped["name"] and not (
            "first_name" in {normalize_column(x) for x in headers} and
            "last_name" in {normalize_column(x) for x in headers}
        ):
            raise ValueError(f"{path.name}: no hay nombre individual reconocible")
        count, seen, no_name, no_club, no_position = 0, set(), 0, 0, 0
        ovrs = []
        fill = {key: 0 for key in CORE_ALIASES}
        for number, row in enumerate(reader, 2):
            count += 1
            raw_id = str(row.get(mapped["fc_player_id"]) or "").strip()
            if not raw_id or not raw_id.isdecimal():
                raise ValueError(f"Fila {number}: ID EA inválido")
            if raw_id in seen:
                raise ValueError(f"Fila {number}: ID duplicado dentro del archivo")
            seen.add(raw_id)
            raw_ovr = str(row.get(mapped["ovr"]) or "").strip()
            ovrs.append(validate_rating(raw_ovr, "OVR", number))
            if ovrs[-1] is None:
                raise ValueError(f"Fila {number}: OVR faltante")
            for key, column in mapped.items():
                if column and str(row.get(column) or "").strip():
                    fill[key] += 1
            name = str(row.get(mapped["name"]) or "").strip() if mapped["name"] else ""
            if not name:
                lowered = {normalize_column(k): v for k, v in row.items()}
                name = (str(lowered.get("first_name") or "") + " " +
                        str(lowered.get("last_name") or "")).strip()
            no_name += not bool(name)
            no_club += not bool(mapped["club"] and str(row.get(mapped["club"]) or "").strip())
            no_position += not bool(mapped["position"] and str(row.get(mapped["position"]) or "").strip())
            for metric in ("pac", "sho", "pas", "dri", "def", "phy"):
                column = mapped[metric]
                if column:
                    validate_rating(row.get(column), metric, number)
        if count == 0:
            raise ValueError(f"Archivo sin jugadores: {path.name}")
    size = path.stat().st_size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cols = [normalize_column(h) for h in headers]
    return {
        "file": path.name, "rows": count, "columns": len(headers),
        "column_names": headers, "mapped_core_columns": mapped,
        "detailed_attributes_detected": [x for x in DETAIL_ALIASES if x in cols],
        "ovr_min": min(ovrs), "ovr_max": max(ovrs),
        "missing_name": no_name, "missing_club": no_club,
        "missing_position": no_position,
        "nonempty_core_fields": fill, "file_bytes": size,
        "sha256": digest,
    }


def inspect_directory(root: Path, checked_at: str | None = None) -> dict:
    files = sorted(root.rglob("*.csv"))
    if not files:
        raise FileNotFoundError("Kaggle devolvió un directorio sin archivos CSV")
    summaries = []
    failures = []
    for path in files:
        try:
            summaries.append(inspect_csv(path))
        except ValueError as exc:
            failures.append({"file": path.name, "error": str(exc)})
    if not summaries:
        raise ValueError("Ningún CSV tiene campos de jugador/OVR identificables: " + str(failures))
    report = {
        "dataset": DATASET, "url": DATASET_URL,
        "retrieved_at_utc": checked_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "edition_claimed": "FC27",
        "source": "Dataset publicado por tercero en Kaggle (no publicación oficial EA)",
        "snapshot_date_claimed": "2026-09-12",
        "snapshot_date_verified_in_files": False,
        "license_verified": False,
        "redistribution_authorized": False,
        "ready_to_join_players": False,
        "downloaded_but_not_redistributed": True,
        "candidate_csv": summaries,
        "other_csv_not_recognized_as_ratings": failures,
        "warning": "Antes de entrenar o redistribuir: verificar derechos, autenticidad, fecha, y tabla de ID EA -> ID deportivo.",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditar EA FC27 de Kaggle: solo metadatos")
    parser.add_argument("--local-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=Path("outputs/auditoria_kaggle_fc27.json"))
    args = parser.parse_args()
    if args.local_dir:
        folder = args.local_dir
    else:
        try:
            import kagglehub
        except ImportError as exc:
            raise SystemExit("Falta kagglehub: pip install kagglehub") from exc
        folder = Path(kagglehub.dataset_download(DATASET))
    report = inspect_directory(folder)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "dataset": DATASET, "csv_validos": len(report["candidate_csv"]),
        "total_registros_por_archivo": {
            x["file"]: x["rows"] for x in report["candidate_csv"]
        },
        "total_columnas_por_archivo": {
            x["file"]: x["columns"] for x in report["candidate_csv"]
        },
        "licencia_verificada": False, "listo_para_modelo": False,
        "informe": str(args.report),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
