#!/usr/bin/env python3
"""Construye datasets maestros auditables, sin ejecutar entrenamiento.

Tablas públicas: partidos 1X2, goles observados, goleadores observados y
reporte de calidad. No incluyen valoraciones de EA FC (privadas). Las
variables de un encuentro deben provenir de fechas anteriores al mismo.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scripts.build_live_features import FEATURES, build_features
from scripts.build_scorer_summary import COLUMNS as SCORER_COLUMNS, observed_scorers
from scripts.link_fc27_openligadb import team_for_goal_events

SOURCE = "OpenLigaDB (ODbL-1.0)"
FEATURE_COLUMNS = [f"{side}_{key}" for side in ("home", "away") for key in FEATURES]
MATCH_COLS = [
    "league", "season_start_year", "match_id", "kickoff_utc",
    "home_id", "home_team", "away_id", "away_team",
    *FEATURE_COLUMNS,
    "pre_match_min3_each", "record_status",
    "target_1x2_postmatch", "home_goals_postmatch", "away_goals_postmatch",
    "eligible_1x2_research", "source_snapshot_utc", "source_url",
]
GOAL_COLS = [
    "league", "season_start_year", "match_id", "goal_event_sequence",
    "player_id_openligadb", "player_name", "club_inferred",
    "club_inference_status", "minute", "is_penalty", "is_own_goal",
    "home_score_after_goal", "away_score_after_goal",
    "source_snapshot_utc", "event_is_postmatch_only", "source",
]
MAX_MISSING_RESEARCH = 0


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def parse_utc(value: str) -> datetime:
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Fecha de origen sin zona horaria")
    return result.astimezone(timezone.utc)


def match_key(row):
    return (str(row["league"]), str(row["season_start_year"]), str(row["match_id"]))


def is_true(value) -> bool:
    return str(value).strip().lower() == "true"


def check_sha256(path: Path, sha: str):
    if sha and hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError(f"Checksum histórico inválido: {path.name}")


def validate_one_season(raw: list[dict], featured: list[dict],
                        checked: str, *, label: str) -> list[dict]:
    """Validate match IDs, pre-match snapshots and all 12 historical features.

    Recompute pre-match features from original fixtures, not from labels.
    In case of any discrepancy, stop before persisting master data.
    """
    if len(raw) != len(featured):
        raise ValueError(f"{label}: resultados vs features con cantidad diferente")
    observed = {}
    for row in raw:
        key = match_key(row)
        if key in observed:
            raise ValueError(f"{label}: partido duplicado {key}")
        observed[key] = row
    feature_map = {}
    for row in featured:
        key = match_key(row)
        if key in feature_map:
            raise ValueError(f"{label}: features duplicadas {key}")
        feature_map[key] = row
        if parse_utc(row["as_of_utc"]) != parse_utc(checked):
            raise ValueError(f"{label}: fecha de features distinta del snapshot")
    if observed.keys() != feature_map.keys():
        raise ValueError(f"{label}: partidos y features sin correspondencia")
    recomputed = {match_key(m): m for m in build_features(raw, checked)}
    result = []
    for key, match in observed.items():
        vals = feature_map[key]
        calculated = recomputed[key]
        for field in FEATURE_COLUMNS + ["target_1x2", "both_teams_min3_prior"]:
            expected, actual = str(calculated.get(field, "")), str(vals.get(field, ""))
            if expected != actual:
                raise ValueError(f"{label}: valor prepartido inconsistente {field} en {key}")
        for field in ("home_id", "away_id", "kickoff_utc"):
            if str(match[field]) != str(vals[field]):
                raise ValueError(f"{label}: identificador de fixture incoherente {field}")
        match_kickoff = parse_utc(match["kickoff_utc"])
        source_date = parse_utc(checked)
        finished = is_true(match["finished"])
        target = str(vals.get("target_1x2") or "")
        if target and (not finished or match_kickoff > source_date):
            raise ValueError(f"{label}: etiqueta de partido futuro o no finalizado")
        if finished:
            # Labels are never feature columns; validate with original final score.
            if target not in ("H", "D", "A"):
                raise ValueError(f"{label}: resultado final sin etiqueta")
            h, a = int(match["home_goals"]), int(match["away_goals"])
            expected = "H" if h > a else "A" if h < a else "D"
            if target != expected or match.get("outcome") != expected:
                raise ValueError(f"{label}: ganador incoherente con marcador")
        else:
            if target or match.get("outcome") in ("H", "D", "A"):
                raise ValueError(f"{label}: etiqueta de partido por jugar")
        min3 = is_true(vals["both_teams_min3_prior"])
        row = {
            "league": key[0], "season_start_year": key[1],
            "match_id": key[2], "kickoff_utc": match["kickoff_utc"],
            "home_id": match["home_id"], "home_team": match["home_team"],
            "away_id": match["away_id"], "away_team": match["away_team"],
            **{field: vals.get(field, "") for field in FEATURE_COLUMNS},
            "pre_match_min3_each": str(min3),
            "record_status": "FINISHED" if finished else "UNPLAYED",
            "target_1x2_postmatch": target,
            "home_goals_postmatch": match["home_goals"] if finished else "",
            "away_goals_postmatch": match["away_goals"] if finished else "",
            "eligible_1x2_research": str(bool(finished and min3)),
            "source_snapshot_utc": checked,
            "source_url": match.get("source_url") or SOURCE,
        }
        result.append(row)
    return result


def load_sources(current_dir: Path, historical_dir: Path):
    current_meta = json.loads((current_dir / "ultima_actualizacion.json").read_text(encoding="utf-8"))
    if current_meta.get("license") != "ODbL-1.0":
        raise ValueError("Licencia de fuente actual no esperada")
    sources = []
    for entry in current_meta["leagues"]:
        prefix = f"{entry['league']}_{entry['season']}"
        raw = read_csv(current_dir / f"{prefix}_partidos.csv")
        features = read_csv(current_dir / f"{prefix}_features_prepartido.csv")
        if len(raw) != entry["matches"]:
            raise ValueError(f"Manifest de temporada actual erróneo: {prefix}")
        goals = read_csv(current_dir / f"{prefix}_goleadores.csv")
        if len(goals) != entry["goal_events"]:
            raise ValueError(f"Cantidad de eventos de gol no coincide: {prefix}")
        sources.append((prefix, current_meta["checked_at_utc"], raw, features, goals, False))
    hist_manifest = historical_dir / "manifest.json"
    if hist_manifest.exists():
        meta = json.loads(hist_manifest.read_text(encoding="utf-8"))
        if meta.get("license") != "ODbL-1.0":
            raise ValueError("Licencia histórica inesperada")
        for entry in meta["leagues"]:
            prefix = f"{entry['league']}_{entry['season']}"
            raw_path = historical_dir / f"{prefix}_partidos.csv"
            features_path = historical_dir / f"{prefix}_features_prepartido.csv"
            check_sha256(raw_path, entry.get("matches_sha256", ""))
            check_sha256(features_path, entry.get("features_sha256", ""))
            raw, features = read_csv(raw_path), read_csv(features_path)
            if len(raw) != entry["matches"]:
                raise ValueError(f"Manifest histórico erróneo: {prefix}")
            # El histórico actual no trae eventos de jugadores.
            sources.append((prefix, meta["checked_at_utc"], raw, features, [], True))
    return sources, current_meta


def build_master(current_dir: Path, historical_dir: Path, output_dir: Path):
    sources, current_meta = load_sources(current_dir, historical_dir)
    all_matches = []
    all_goals = []
    all_scorers = []
    reports = []
    all_keys = set()
    for prefix, checked, original, features, events, archived in sources:
        rows = validate_one_season(original, features, checked, label=prefix)
        for row in rows:
            key = match_key(row)
            if key in all_keys:
                raise ValueError("Partido duplicado en varias fuentes")
            all_keys.add(key)
        all_matches.extend(rows)
        inferred, evidence = team_for_goal_events(original, events)
        # Una sola evidencia por evento, usando la misma llave del gol original
        # cuando la secuencia completa de marcadores es válida.
        inferred_keys = {}
        for event in inferred:
            k = (event["league"], event["season"], event["match_id"],
                 event["openligadb_player_id"], event["openligadb_player_name"],
                 event["is_own_goal"], event["is_penalty"])
            inferred_keys.setdefault(k, []).append(event["club"])
        for seq, event in enumerate(events, 1):
            key = (
                event["league"], str(event["season_start_year"]), str(event["match_id"]),
                str(event.get("player_id") or "").strip(), str(event.get("player_name") or "").strip(),
                is_true(event.get("is_own_goal", "")), is_true(event.get("is_penalty", "")),
            )
            clubs = inferred_keys.get(key, [])
            club = clubs.pop(0) if clubs else ""
            all_goals.append({
                "league": key[0], "season_start_year": key[1], "match_id": key[2],
                "goal_event_sequence": seq,
                "player_id_openligadb": key[3], "player_name": key[4],
                "club_inferred": club,
                "club_inference_status": "COMPLETE_SCORE_SEQUENCE" if club else "UNKNOWN",
                "minute": event.get("minute", ""),
                "is_penalty": str(key[6]), "is_own_goal": str(key[5]),
                "home_score_after_goal": event.get("home_score_after_goal", ""),
                "away_score_after_goal": event.get("away_score_after_goal", ""),
                "source_snapshot_utc": checked,
                "event_is_postmatch_only": "True",
                "source": "OpenLigaDB ODbL-1.0",
            })
        if not archived:
            summaries, summary_report = observed_scorers(original, events, checked)
            all_scorers.extend(summaries)
        else:
            summary_report = {"all_players_roster_coverage": False, "reason": "No se descargaron goles de temporadas históricas"}
        reports.append({
            "season": prefix, "source_snapshot_utc": checked,
            "match_rows": len(rows),
            "finished": sum(row["record_status"] == "FINISHED" for row in rows),
            "research_eligible_1x2": sum(is_true(row["eligible_1x2_research"]) for row in rows),
            "goal_event_rows": len(events),
            "goal_events_with_club": sum(e["club_inference_status"] == "COMPLETE_SCORE_SEQUENCE"
                                         for e in all_goals if f"{e['league']}_{e['season_start_year']}" == prefix),
            "scorer_rows": 0 if archived else len(summaries),
            "archived": archived,
            "player_stats_coverage": summary_report,
        })
    all_matches.sort(key=lambda x: (x["kickoff_utc"], x["league"], x["match_id"]))
    all_goals.sort(key=lambda x: (x["league"], x["season_start_year"], x["match_id"], x["goal_event_sequence"]))
    all_scorers.sort(key=lambda x: (x["league"], x["season_start_year"], x["openligadb_player_id"]))
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_source_snapshot_utc": current_meta["checked_at_utc"],
        "source": "OpenLigaDB", "license": "ODbL-1.0",
        "tables": {
            "master_partidos.csv": len(all_matches),
            "master_eventos_gol.csv": len(all_goals),
            "master_goleadores_observados.csv": len(all_scorers),
        },
        "research_eligible_1x2_rows": sum(is_true(row["eligible_1x2_research"]) for row in all_matches),
        "finished_rows": sum(row["record_status"] == "FINISHED" for row in all_matches),
        "by_season": reports,
        "quality_checks_passed": True,
        "fifa_fc27_catalog_status": "PRIVATE_SEPARATE_CATALOG_ONLY_NOT_MERGED_IN_PUBLIC_MASTER",
        "fifa_fc27_verified_player_id_links": 0,
        "has_complete_player_match_stats": False,
        "has_verified_player_shots_minutes_cards": False,
        "has_current_xg_all_leagues": False,
        "ready_for_final_player_models": False,
        "ready_for_final_betting_models": False,
        "notes": [
            "Etiquetas y marcadores postpartido son columnas separadas, nunca features.",
            "Un goleador ausente del dataset NO tiene cero tiros ni cero minutos.",
            "Solo se identifica el club del goleador cuando la secuencia de goles coincide con el marcador final.",
            "Las valoraciones EA FC27 permanecen privadas; falta verificar identidades entre proveedores.",
            "Datos de OpenLigaDB son comunitarios; se necesita comprobación externa para competiciones reales.",
        ],
    }
    # No crear ficheros parciales si alguna validación anterior falló.
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "master_partidos.csv", MATCH_COLS, all_matches)
    write_csv(output_dir / "master_eventos_gol.csv", GOAL_COLS, all_goals)
    write_csv(output_dir / "master_goleadores_observados.csv", SCORER_COLUMNS, all_scorers)
    for name in report["tables"]:
        report.setdefault("sha256", {})[name] = hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
    (output_dir / "calidad_y_cobertura.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Construir maestro versionado, SIN entrenamiento")
    parser.add_argument("--current", type=Path, default=Path("datasets/actualizados"))
    parser.add_argument("--historical", type=Path, default=Path("datasets/historicos"))
    parser.add_argument("--output", type=Path, default=Path("datasets/maestro"))
    args = parser.parse_args()
    report = build_master(args.current, args.historical, args.output)
    print(json.dumps({
        "rows": report["tables"], "quality_checks_passed": report["quality_checks_passed"],
        "research_eligible_1x2": report["research_eligible_1x2_rows"],
        "ready_for_final_player_models": False, "ready_for_final_betting_models": False,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
