#!/usr/bin/env python3
"""Audita SOLO metadatos del lago de fútbol publicado en Hugging Face.

NO descarga tablas masivas de partidos/jugadores, NO las redistribuye,
NO las incorpora al maestro ni entrena modelos. Descargar únicamente:
README, data_dictionary, datapackage, QUALITY_REPORT y
league_catalogue.parquet (~40 KB). El material deriva de API-Football
y football-data.co.uk; los permisos aguas arriba deben aclararse aparte.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata

DATASET = "eatpizzanot/soccer-dataset"
DATASET_URL = "https://huggingface.co/datasets/" + DATASET
METADATA_FILES = (
    "README.md", "data_dictionary.md", "datapackage.json",
    "QUALITY_REPORT.md", "league_catalogue.parquet",
)
EXPECTED_TABLES = (
    "fixtures", "players", "fixture_players",
    "fixture_players_stats_flat", "match_stats", "league_catalogue",
)
REQUIRED_FIELDS = {
    "fixtures": {"id", "league_id", "date_utc"},
    "fixture_players": {"fixture_id", "player_id", "team_id"},
    "fixture_players_stats_flat": {"fixture_id", "player_id", "games_minutes", "shots_total"},
    "league_catalogue": {"af_country", "af_name", "history_status", "in_dataset"},
}


def simplify(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def pick_target(row: dict) -> str | None:
    country = simplify(row.get("af_country"))
    league = simplify(row.get("af_name"))
    if country == "spain" and league in ("la liga", "primera division", "laliga"):
        return "la1"
    if country == "germany" and league in ("bundesliga", "1. bundesliga"):
        return "bl1"
    return None


def safe_value(value):
    """No inventar cero cuando un campo no existe o es nulo."""
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def analyze_catalogue(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("league_catalogue está vacío")
    required = REQUIRED_FIELDS["league_catalogue"]
    if not required.issubset(set(rows[0])):
        raise ValueError("Columnas obligatorias ausentes del catálogo de ligas")
    targets = {"la1": [], "bl1": []}
    for row in rows:
        target = pick_target(row)
        if target:
            targets[target].append({
                "provider_league_id": safe_value(row.get("af_league_id")),
                "provider_name": safe_value(row.get("af_name")),
                "country": safe_value(row.get("af_country")),
                "in_dataset": safe_value(row.get("in_dataset")),
                "history_status": safe_value(row.get("history_status")),
                "first_season_claimed": safe_value(row.get("min_season")),
                "last_season_claimed": safe_value(row.get("max_season")),
                "years_present_claimed": safe_value(row.get("present_years")),
                "provider_has_stats_claimed": safe_value(row.get("af_has_stats")),
            })
    return {
        "catalogue_rows": len(rows),
        "selected_leagues": targets,
        "selection_status": {
            key: "FOUND_CATALOGUE_ONLY" if items else "NOT_FOUND_IN_CATALOGUE"
            for key, items in targets.items()
        },
        "cannot_infer_from_catalogue": [
            "Cantidad por temporada de minutos, tiros o tarjetas por futbolista",
            "Porcentaje de estadísticas completas en LaLiga/Bundesliga específicamente",
            "Disponibilidad de datos antes de cada partido",
            "Compatibilidad entre IDs de proveedores",
        ],
    }


def inspect_schema(data_package: dict) -> dict:
    resources = data_package.get("resources", [])
    if not isinstance(resources, list):
        raise ValueError("datapackage.json no tiene resources válidos")
    tables = {}
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        name = resource.get("name") or Path(str(resource.get("path", ""))).stem
        fields = resource.get("schema", {}).get("fields", [])
        columns = {field.get("name") for field in fields if isinstance(field, dict)}
        if name in EXPECTED_TABLES:
            tables[name] = {
                "present_in_metadata": True,
                "declared_rows": resource.get("rows"),
                "column_count_declared": len(columns),
                "essential_columns_present": sorted(REQUIRED_FIELDS.get(name, set()) & columns),
                "essential_columns_missing": sorted(REQUIRED_FIELDS.get(name, set()) - columns),
            }
    for name in EXPECTED_TABLES:
        if name not in tables:
            tables[name] = {
                "present_in_metadata": False,
                "declared_rows": None, "column_count_declared": None,
                "essential_columns_present": [],
                "essential_columns_missing": sorted(REQUIRED_FIELDS.get(name, set())),
            }
    return tables


def build_report(catalogue_rows: list[dict], package: dict, revision: str,
                 source_documents: list[str], timestamp: str | None = None):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Revisión no es SHA40 fijo de Hugging Face")
    catalogue = analyze_catalogue(catalogue_rows)
    tables = inspect_schema(package)
    return {
        "repository": DATASET,
        "repository_url": DATASET_URL,
        "revision_sha": revision,
        "audited_at_utc": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "METADATA_ONLY",
        "files_inspected": sorted(set(source_documents)),
        "large_data_files_downloaded": False,
        "upstream_sources_declared": ["API-Football", "football-data.co.uk"],
        "declared_dataset_license": "CC-BY-4.0",
        "upstream_use_rights_verified": False,
        "commercial_ml_clearance_verified": False,
        "redistribution_clearance_verified": False,
        "approved_for_master_dataset": False,
        "approved_for_model_training": False,
        "league_catalogue": catalogue,
        "schema": tables,
        "data_quality_status": "UNVERIFIED_FOR_TARGET_LEAGUES",
        "next_action": (
            "Solicitar derechos para uso específico por fuente y realizar auditoría"
            " privada de cobertura partido-jugador con data autorizada."
        ),
        "notes": [
            "La licencia declarada por un agregador no demuestra derechos sobre fuentes previas.",
            "No se descarga ningún archivo masivo con eventos, ratings o estadísticas individuales.",
            "El diccionario y el catálogo describen campos y ligas, pero no prueban cobertura efectiva.",
            "No convertir nulos a ceros ni confundir xG por zonas con xG de cada disparo.",
            "SoccerNet se enfoca en vídeo; no sustituye la tabla tabular por jugador y partido.",
        ],
    }


def download_metadata():
    try:
        from huggingface_hub import HfApi, hf_hub_download
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit("Instala dependencias de auditoría: huggingface_hub y pyarrow") from exc

    info = HfApi().dataset_info(DATASET)
    revision = info.sha
    if not re.fullmatch(r"[a-f0-9]{40}", str(revision)):
        raise ValueError("No se pudo fijar una revisión íntegra de la fuente")
    existing = {f.rfilename for f in info.siblings}
    missing = set(METADATA_FILES) - existing
    if missing:
        raise ValueError("Faltan ficheros metadata: " + ", ".join(sorted(missing)))

    paths = {}
    for name in METADATA_FILES:
        paths[name] = Path(hf_hub_download(
            repo_id=DATASET, repo_type="dataset", filename=name, revision=revision
        ))
    package = json.loads(paths["datapackage.json"].read_text(encoding="utf-8"))
    table = pq.read_table(paths["league_catalogue.parquet"])
    if table.num_rows > 100_000:
        raise ValueError("Catálogo de ligas demasiado grande para auditoría limitada")
    rows = table.to_pylist()
    # No se publican las filas originales ni artefactos de terceros.
    return build_report(rows, package, revision, list(paths))


def main():
    parser = argparse.ArgumentParser(description="Auditar metadata HF, sin descargar datasets masivos")
    parser.add_argument("--out", type=Path, default=Path("outputs/auditoria_hf_soccer.json"))
    args = parser.parse_args()
    result = download_metadata()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    compact = {
        "dataset": result["repository"],
        "revision": result["revision_sha"],
        "catalogue_rows": result["league_catalogue"]["catalogue_rows"],
        "target_leagues": result["league_catalogue"]["selected_leagues"],
        "table_schema_summary": result["schema"],
        "source_rights_verified": result["upstream_use_rights_verified"],
        "approved_for_training": result["approved_for_model_training"],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
