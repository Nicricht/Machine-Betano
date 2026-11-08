#!/usr/bin/env python3
"""Catálogo privado FIFA FC27 + goleadores OL, sin identidad por nombre.

Solo asocia ratings a un futbolista cuando existe una tabla de equivalencias
revisada por una persona con evidencia externa. En ausencia de esa tabla,
los ratings FIFA quedan en su propio catálogo y los jugadores sin completar.
Nunca se usa este resultado para partidos anteriores a la fecha del rating.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path

COLUMNS = [
    "league", "season_start_year", "openligadb_player_id", "player_name",
    "observed_club", "scoring_matches", "goals_reported",
    "fc_player_id_verified", "fc_name_verified", "fc_club_snapshot",
    "fc_edition", "fc_as_of_date",
    "ovr", "pac", "sho", "pas", "dri", "def", "phy",
    "identity_status", "evidence_url", "reviewed_by", "reviewed_on",
]
MAP_COLUMNS = (
    "league", "openligadb_player_id", "fc_player_id",
    "review_status", "evidence_url", "reviewed_by", "reviewed_on",
)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def approved_map(path: Path, fifa: dict) -> dict:
    if not path.exists():
        return {}
    rows = read_csv(path)
    out = {}
    used_fc = {}
    for line, row in enumerate(rows, 2):
        if not set(MAP_COLUMNS).issubset(row):
            raise ValueError("Mapeo sin columnas de evidencia y revisión")
        if row["review_status"] != "VERIFIED":
            raise ValueError(f"Fila {line}: review_status distinto de VERIFIED")
        key = (row["league"].strip(), row["openligadb_player_id"].strip())
        fc_id = row["fc_player_id"].strip()
        reviewer = row["reviewed_by"].strip()
        source = row["evidence_url"].strip()
        try:
            date.fromisoformat(row["reviewed_on"])
        except ValueError as exc:
            raise ValueError(f"Fila {line}: reviewed_on no válido") from exc
        if not key[0] or not key[1].isdecimal() or not fc_id.isdecimal() or not reviewer:
            raise ValueError(f"Fila {line}: faltan IDs o revisor")
        if not source.startswith("https://"):
            raise ValueError(f"Fila {line}: evidencia externa HTTPS obligatoria")
        if fc_id not in fifa:
            raise ValueError(f"Fila {line}: ID FC no existe en catálogo actual")
        if key in out:
            raise ValueError(f"Fila {line}: un jugador deportivo con más de un ID FC")
        # Si la misma ficha EA se asigna a 2 futbolistas OpenLigaDB, detener.
        if fc_id in used_fc and used_fc[fc_id] != key:
            raise ValueError(f"Fila {line}: colisión entre IDs de distintas fuentes")
        used_fc[fc_id] = key
        out[key] = row
    return out


def integrate(ratings: Path, sports_players: Path, reviewed_map: Path, output_dir: Path):
    fifa_records = read_csv(ratings)
    fifa = {}
    for player in fifa_records:
        pid = player["fc_player_id"]
        if not pid.isdecimal() or pid in fifa:
            raise ValueError("ID FIFA vacío, no numérico o duplicado")
        if player["edition"] != "FC27":
            raise ValueError("El dataset FIFA contiene una edición distinta a FC27")
        date.fromisoformat(player["as_of_date"])
        fifa[pid] = player
    verified = approved_map(reviewed_map, fifa)
    sports = read_csv(sports_players)
    result = []
    linked_keys = set()
    for person in sports:
        key = (person["league"], person["openligadb_player_id"])
        # Puede haber dos clubes por traspaso, pero no dos perfiles EA.
        mapping = verified.get(key)
        player = fifa[mapping["fc_player_id"]] if mapping else {}
        if mapping:
            linked_keys.add(key)
        result.append({
            "league": person["league"],
            "season_start_year": person["season_start_year"],
            "openligadb_player_id": person["openligadb_player_id"],
            "player_name": person["openligadb_player_name"],
            "observed_club": person["observed_club"],
            "scoring_matches": person["scoring_matches"],
            "goals_reported": person["goals_reported"],
            "fc_player_id_verified": player.get("fc_player_id", ""),
            "fc_name_verified": player.get("name", ""),
            "fc_club_snapshot": player.get("club", ""),
            "fc_edition": player.get("edition", ""),
            "fc_as_of_date": player.get("as_of_date", ""),
            **{x: player.get(x, "") for x in ("ovr", "pac", "sho", "pas", "dri", "def", "phy")},
            "identity_status": "VERIFIED_BY_REVIEWER_NOT_INDEPENDENTLY_AUDITED" if mapping else "UNLINKED",
            "evidence_url": mapping["evidence_url"] if mapping else "",
            "reviewed_by": mapping["reviewed_by"] if mapping else "",
            "reviewed_on": mapping["reviewed_on"] if mapping else "",
        })
    # No permitir un mapeo aprobado que ni siquiera aparece en la muestra
    # deportiva actual: puede ser antiguo o referirse a otra liga/temporada.
    missing = set(verified) - linked_keys
    if missing:
        raise ValueError(f"{len(missing)} correspondencias revisadas no figuran en fuente deportiva")
    output_dir.mkdir(parents=True, exist_ok=True)
    private = output_dir / "master_fc27_jugadores_verificados.csv"
    with private.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(result)
    report = {
        "fc27_catalog_rows": len(fifa),
        "sports_scorer_rows": len(sports),
        "verified_provider_id_pairs_supplied": len(verified),
        "linked_scorer_rows": sum(bool(row["fc_player_id_verified"]) for row in result),
        "missing_id_mappings": len(sports) - sum(bool(row["fc_player_id_verified"]) for row in result),
        "fc_license_redistribution_verification": "NOT_CHECKED_BY_PIPELINE",
        "fifa_ratings_available_before_each_historical_match": False,
        "match_player_minutes_or_shots_available": False,
        "ready_for_player_match_training": False,
        "warnings": [
            "No se realiza matching automático por nombre o club.",
            "Mapeos provistos por revisores requieren evidencias independientes reales.",
            "El dataset contiene valoración de una fecha, no series prepartido históricas.",
            "Este CSV es privado; no publicar ratings de terceros por defecto.",
        ],
    }
    (output_dir / "master_fc27_cobertura.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Enriquecer goleadores solo con IDs FIFA revisados")
    parser.add_argument("--ratings", type=Path, default=Path("datasets/ratings/fc_ratings.csv"))
    parser.add_argument("--players", type=Path, default=Path("datasets/maestro/master_goleadores_observados.csv"))
    parser.add_argument("--map", type=Path, default=Path("datasets/ratings/id_map_verificados.csv"))
    parser.add_argument("--output", type=Path, default=Path("datasets/ratings"))
    args = parser.parse_args()
    report = integrate(args.ratings, args.players, args.map, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
