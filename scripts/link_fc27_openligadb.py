#!/usr/bin/env python3
"""Cruce conservador entre jugadores EA FC27 y goleadores OpenLigaDB.

No supone IDs compatibles. Requiere coincidencia de equipo, nombre e
identificadores unívocos. Cada resultado automático es PROVISIONAL y necesita
revisión para usarse como feature o para entrenar modelos.

Los datos de terceros permanecen en ficheros privados ignorados por git.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata


LINK_COLUMNS = [
    "league", "season", "openligadb_player_id", "openligadb_player_name",
    "openligadb_club", "fc_player_id", "fc_player_name", "fc_club",
    "edition", "rating_as_of_date", "match_basis", "scoring_events",
    "evidence_matches", "review_status",
]


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss").replace("ø", "o").replace("ł", "l")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def scorer_style(scorer: str, fc_name: str) -> str | None:
    """Exacto o inicial+apellido; apellidos solos requieren revisión."""
    source = normalize_name(scorer).split()
    fc = normalize_name(fc_name).split()
    if not source or not fc:
        return None
    if source == fc:
        return "FULL_NAME_EXACT"
    if len(source) >= 2 and len(fc) >= 2:
        if (len(source[0]) == 1 and source[0] == fc[0][0]
                and source[1:] == fc[-len(source) + 1:]):
            return "INITIAL_SURNAME"
    if len(source) == 1 and len(fc) >= 2 and source[0] == fc[-1]:
        return "SURNAME_ONLY"
    return None


def team_for_goal_events(matches: list[dict], goals: list[dict]):
    """Reconstruir equipo del jugador solo cuando la progresión lo demuestra.

    La sucesión de marcadores parciales permite saber qué equipo se beneficia
    del gol. En autogoles, el goleador juega en el equipo OPUESTO.
    Si hay eventos omitidos, duplicados o saltos, descartar todo el partido.
    """
    match_by_id = {
        (m["league"], str(m["season_start_year"]), str(m["match_id"])): m
        for m in matches
    }
    grouped = defaultdict(list)
    for row in goals:
        key = (row["league"], str(row["season_start_year"]), str(row["match_id"]))
        if key in match_by_id:
            grouped[key].append(row)
    evidence = []
    invalid_matches = 0
    total_events = len(goals)
    for key, events in grouped.items():
        match = match_by_id[key]
        try:
            order = sorted(
                events,
                key=lambda g: (int(g["home_score_after_goal"])
                               + int(g["away_score_after_goal"])),
            )
        except (ValueError, TypeError, KeyError):
            invalid_matches += 1
            continue
        h, a = 0, 0
        matched = []
        valid = True
        for event in order:
            h1, a1 = int(event["home_score_after_goal"]), int(event["away_score_after_goal"])
            if (h1 - h, a1 - a) == (1, 0):
                beneficiary = "home"
            elif (h1 - h, a1 - a) == (0, 1):
                beneficiary = "away"
            else:
                valid = False
                break
            h, a = h1, a1
            own_goal = str(event.get("is_own_goal", "")).casefold() == "true"
            scorer_side = ("away" if beneficiary == "home" else "home") if own_goal else beneficiary
            if not str(event.get("player_id") or "").strip():
                continue
            matched.append({
                "league": key[0], "season": key[1],
                "openligadb_player_id": str(event["player_id"]).strip(),
                "openligadb_player_name": str(event.get("player_name") or "").strip(),
                "club": str(match.get(scorer_side + "_team") or "").strip(),
                "match_id": key[2],
                "is_own_goal": own_goal,
                "is_penalty": str(event.get("is_penalty", "")).casefold() == "true",
            })
        if not valid or not matched:
            invalid_matches += 1
            continue
        # No validar un partido con secuencia parcial de eventos de gol.
        try:
            final_h, final_a = int(match["home_goals"]), int(match["away_goals"])
        except (ValueError, KeyError):
            invalid_matches += 1
            continue
        if (h, a) != (final_h, final_a):
            invalid_matches += 1
            continue
        evidence.extend(matched)
    return evidence, {
        "source_goal_events": total_events,
        "goal_events_with_team_inferred": len(evidence),
        "matches_with_incomplete_or_invalid_goal_sequence": invalid_matches,
    }


def propose_links(ratings: list[dict], matches: list[dict], goals: list[dict]):
    ids = set()
    by_club = defaultdict(list)
    for row in ratings:
        pid = str(row.get("fc_player_id") or "").strip()
        if not pid:
            raise ValueError("ID EA FC vacío")
        if pid in ids:
            raise ValueError("ID EA FC duplicado")
        ids.add(pid)
        club = normalize_name(row.get("club", ""))
        if club:
            by_club[club].append(row)

    evidence, coverage = team_for_goal_events(matches, goals)
    by_player = defaultdict(list)
    for row in evidence:
        by_player[(row["league"], row["season"], row["openligadb_player_id"])].append(row)

    proposals = []
    status_count = defaultdict(int)
    no_club = 0
    no_name = 0
    identity_conflicts = 0
    for (league, season, ol_id), events in sorted(by_player.items()):
        seen_ea = {}
        clubs_found = {normalize_name(e["club"]) for e in events}
        clubs_matched = any(by_club.get(club) for club in clubs_found)
        if not clubs_matched:
            no_club += 1
            continue
        for event in events:
            club_key = normalize_name(event["club"])
            for player in by_club.get(club_key, []):
                kind = scorer_style(event["openligadb_player_name"], player.get("name", ""))
                if kind:
                    pid = str(player["fc_player_id"])
                    old = seen_ea.get(pid)
                    if not old or (
                        ("FULL_NAME_EXACT", "INITIAL_SURNAME", "SURNAME_ONLY").index(kind)
                        < ("FULL_NAME_EXACT", "INITIAL_SURNAME", "SURNAME_ONLY").index(old[0])
                    ):
                        seen_ea[pid] = (kind, player, event)
        if not seen_ea:
            no_name += 1
            continue
        ambiguous = len(seen_ea) > 1
        if ambiguous:
            identity_conflicts += 1
        for pid, (kind, player, event) in sorted(seen_ea.items()):
            status = (
                "REVIEW_AMBIGUOUS" if ambiguous else
                "PROVISIONAL_EXACT" if kind == "FULL_NAME_EXACT" else
                "REVIEW_INITIAL_SURNAME" if kind == "INITIAL_SURNAME" else
                "REVIEW_SURNAME_ONLY"
            )
            proposals.append({
                "league": league, "season": season,
                "openligadb_player_id": ol_id,
                "openligadb_player_name": event["openligadb_player_name"],
                "openligadb_club": event["club"],
                "fc_player_id": pid,
                "fc_player_name": str(player["name"]),
                "fc_club": str(player["club"]),
                "edition": str(player.get("edition") or ""),
                "rating_as_of_date": str(player.get("as_of_date") or ""),
                "match_basis": kind,
                "scoring_events": len(events),
                "evidence_matches": len({e["match_id"] for e in events}),
                "review_status": status,
            })
            status_count[status] += 1

    # Un mismo ID de EA no puede asignarse automáticamente a IDs OL distintos.
    reverse = defaultdict(set)
    for row in proposals:
        reverse[row["fc_player_id"]].add((row["league"], row["openligadb_player_id"]))
    collisions = {pid for pid, linked in reverse.items() if len(linked) > 1}
    for row in proposals:
        if row["fc_player_id"] in collisions:
            status_count[row["review_status"]] -= 1
            row["review_status"] = "REVIEW_EA_ID_COLLISION"
            status_count[row["review_status"]] += 1

    report = {
        "fc_players_considered": len(ratings),
        "distinct_scorer_ids_with_team_evidence": len(by_player),
        "proposed_mappings": len(proposals),
        "distinct_openligadb_ids_with_candidate": len({
            (r["league"], r["season"], r["openligadb_player_id"]) for r in proposals
        }),
        "proposals_by_status": dict(sorted(status_count.items())),
        "scorer_ids_without_exact_club": no_club,
        "scorer_ids_without_name_match_at_club": no_name,
        "scorer_ids_ambiguous": identity_conflicts,
        "ea_ids_linked_to_multiple_scorers": len(collisions),
        **coverage,
        "auto_approved_for_training": 0,
        "note": "Todas las equivalencias son propuestas, NO IDs verificados. Revisar antes de usarlas en ML.",
    }
    return proposals, report


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def run(ratings_file: Path, data_dir: Path, output_dir: Path):
    ratings = read_csv(ratings_file)
    if not ratings:
        raise ValueError("Ratings vacíos")
    metadata = json.loads((data_dir / "ultima_actualizacion.json").read_text(encoding="utf-8"))
    matches = []
    goals = []
    for league in metadata["leagues"]:
        k = f"{league['league']}_{league['season']}"
        m = read_csv(data_dir / (k + "_partidos.csv"))
        g = read_csv(data_dir / (k + "_goleadores.csv"))
        if len(m) != league["matches"]:
            raise ValueError("Inconsistencia entre datos y manifiesto de partidos")
        matches.extend(m)
        goals.extend(g)
    proposals, report = propose_links(ratings, matches, goals)
    report.update({
        "ratings_source": "Kaggle user dataset: mikedpad/ea-sports-fc27-player-ratings",
        "sports_source": "OpenLigaDB (ODbL-1.0)",
        "sports_checked_at": metadata.get("checked_at_utc"),
        "audit_created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "license_cleared": False,
        "ready_for_prediction": False,
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "fc27_openligadb_candidates.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LINK_COLUMNS)
        writer.writeheader()
        writer.writerows(proposals)
    (output_dir / "fc27_openligadb_linkage_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description="Proponer equivalencias FC27/OpenLigaDB")
    parser.add_argument("--ratings", type=Path, default=Path("datasets/ratings/fc_ratings.csv"))
    parser.add_argument("--live", type=Path, default=Path("datasets/actualizados"))
    parser.add_argument("--output", type=Path, default=Path("datasets/ratings"))
    args = parser.parse_args()
    report = run(args.ratings, args.live, args.output)
    # No imprimir nombres de jugadores ni ratings restringidos.
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
