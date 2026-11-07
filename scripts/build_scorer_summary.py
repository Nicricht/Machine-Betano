#!/usr/bin/env python3
"""Estadisticas observadas de goleadores OpenLigaDB; no equivale a plantilla.

No atribuir automaticamente minutos, tiros ni partidos sin goles.
Solo cifras observadas en eventos documentados. La distribucion de equipos
se reconstruye de marcadores con controles de consistencia.
"""
from __future__ import annotations

import csv
from collections import defaultdict
import json
from pathlib import Path

from scripts.link_fc27_openligadb import team_for_goal_events

COLUMNS = [
    "league", "season_start_year", "openligadb_player_id",
    "openligadb_player_name", "observed_club", "scoring_matches",
    "goals_reported", "penalty_goals_reported", "own_goals_reported",
    "event_records", "as_of_utc",
    "games_played_known", "minutes_known", "shots_known",
    "source",
]


def observed_scorers(matches: list[dict], goals: list[dict], as_of_utc: str):
    evidence, coverage = team_for_goal_events(matches, goals)
    goal_by_identity = defaultdict(lambda: {
        "matches": set(), "goals": 0, "penalties": 0, "own_goals": 0, "events": 0,
    })
    # Events validly ordered by their post-score are attributed to the correct club.
    raw_goals = {
        (r["league"], str(r["season_start_year"]), str(r["match_id"]),
         str(r.get("player_id") or ""), str(r.get("home_score_after_goal") or ""),
         str(r.get("away_score_after_goal") or "")): r for r in goals
    }
    for event in evidence:
        key = (event["league"], event["season"], event["openligadb_player_id"],
               event["openligadb_player_name"], event["club"])
        values = goal_by_identity[key]
        source = raw_goals.get((event["league"], event["season"],
            event["match_id"], event["openligadb_player_id"],
            # Las puntuaciones no están en evidencia; recuperar este
            # evento por nombre/partido/ID y contarlo con trazabilidad.
            "__unavailable__", "__unavailable__"))
        # Buscar todos los eventos originales de ese jugador y partido
        # en vez de deducir penalty por su nombre.
        values["matches"].add(event["match_id"])
        values["events"] += 1
        if event["is_own_goal"]:
            values["own_goals"] += 1
        else:
            values["goals"] += 1

    # Penaltis: cruzar solo dentro del mismo partido/jugador/club. Cuando
    # hay varios goles, contar el total de penaltis observado sin inferir
    # otros eventos (el equipo ya se dedujo por la secuencia).
    grouped_source = defaultdict(list)
    for g in goals:
        grouped_source[(g["league"], str(g["season_start_year"]),
                        str(g.get("match_id")), str(g.get("player_id")))].append(g)
    for key, rec in goal_by_identity.items():
        league, season, pid, _, club = key
        matches_for_player = rec["matches"]
        penalty_count = 0
        for match in matches_for_player:
            candidates = grouped_source.get((league, season, match, pid), [])
            for event in candidates:
                if (str(event.get("is_penalty", "")).lower() == "true"
                        and str(event.get("is_own_goal", "")).lower() != "true"):
                    penalty_count += 1
        rec["penalties"] = min(rec["goals"], penalty_count)

    rows = []
    for (league, season, pid, name, club), rec in sorted(goal_by_identity.items()):
        rows.append({
            "league": league, "season_start_year": season,
            "openligadb_player_id": pid, "openligadb_player_name": name,
            "observed_club": club,
            "scoring_matches": len(rec["matches"]),
            "goals_reported": rec["goals"],
            "penalty_goals_reported": rec["penalties"],
            "own_goals_reported": rec["own_goals"],
            "event_records": rec["events"],
            "as_of_utc": as_of_utc,
            "games_played_known": "",
            "minutes_known": "",
            "shots_known": "",
            "source": "OpenLigaDB ODbL-1.0",
        })
    coverage.update({
        "observed_unique_scorer_club_rows": len(rows),
        "distinct_scorer_ids": len(set((r["league"], r["season_start_year"],
                                      r["openligadb_player_id"]) for r in rows)),
        "all_players_roster_coverage": False,
        "minutes_shots_participation_available": False,
        "as_of_utc": as_of_utc,
    })
    return rows, coverage


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def run(directory: Path):
    manifest = json.loads((directory / "ultima_actualizacion.json").read_text(encoding="utf-8"))
    out = []
    report = {}
    for league in manifest["leagues"]:
        group = league["league"]
        season = league["season"]
        prefix = f"{group}_{season}"
        matches = read_rows(directory / (prefix + "_partidos.csv"))
        goals = read_rows(directory / (prefix + "_goleadores.csv"))
        if len(matches) != league["matches"]:
            raise ValueError("Partidos distintos del manifiesto")
        rows, coverage = observed_scorers(matches, goals, manifest["checked_at_utc"])
        path = directory / (prefix + "_goleadores_resumen.csv")
        out.append((path, rows))
        report[prefix] = coverage
    for path, rows in out:
        temp = path.with_suffix(".csv.tmp")
        with temp.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        temp.replace(path)
    (directory / "cobertura_jugadores.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return report


def main():
    directory = Path("datasets/actualizados")
    print(json.dumps(run(directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
