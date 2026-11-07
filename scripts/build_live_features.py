#!/usr/bin/env python3
"""Variables prepartido para las ligas actuales de OpenLigaDB.

No requiere paquetes terceros, credenciales ni acceso a casas de apuestas.
Trabaja solo con marcadores de partidos de FECHAS anteriores al encuentro.
Nunca reutiliza el marcador del mismo partido como feature.
"""
from __future__ import annotations

import csv
from collections import defaultdict, deque
from datetime import date, datetime, timezone
import json
from pathlib import Path

FEATURES = (
    "matches_prev", "goals_for_avg5", "goals_against_avg5",
    "points_avg5", "win_rate5", "rest_days",
)
COLUMNS = [
    "league", "season_start_year", "match_id", "kickoff_utc",
    "home_id", "home_team", "away_id", "away_team",
    *["home_" + col for col in FEATURES],
    *["away_" + col for col in FEATURES],
    "target_1x2", "future_fixture", "both_teams_min3_prior",
    "as_of_utc", "source",
]


def iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_features(matches: list[dict], as_of: str, window: int = 5):
    if window <= 0:
        raise ValueError("Ventana debe ser positiva")
    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    if as_of_dt.tzinfo is None:
        raise ValueError("La fecha de extracción debe incluir zona horaria")
    as_of_dt = as_of_dt.astimezone(timezone.utc)
    ids = set()
    normalized = []
    for match in matches:
        key = (str(match["league"]), str(match["season_start_year"]), str(match["match_id"]))
        if key in ids:
            raise ValueError("Match ID duplicado")
        ids.add(key)
        day = iso_date(match.get("kickoff_utc"))
        if day is None:
            raise ValueError(f"Fecha inválida para partido {match.get('match_id')}")
        if not match.get("home_id") or not match.get("away_id"):
            raise ValueError("Equipos sin ID")
        normalized.append((day, match))
    normalized.sort(key=lambda x: (x[0], x[1]["match_id"]))
    history = defaultdict(lambda: deque(maxlen=window))
    last_day = {}
    output = []

    def key_for(match, side):
        return (str(match["league"]), str(match["season_start_year"]), str(match[side + "_id"]))

    def snapshot(match, side, day):
        key = key_for(match, side)
        hist = history[key]
        size = len(hist)
        previous = last_day.get(key)
        return {
            side + "_matches_prev": size,
            side + "_goals_for_avg5": round(sum(row[0] for row in hist) / size, 4) if size else "",
            side + "_goals_against_avg5": round(sum(row[1] for row in hist) / size, 4) if size else "",
            side + "_points_avg5": round(sum(row[2] for row in hist) / size, 4) if size else "",
            side + "_win_rate5": round(sum(row[3] for row in hist) / size, 4) if size else "",
            side + "_rest_days": (day - previous).days if previous else "",
        }

    days = sorted(set(d for d, _ in normalized))
    for day in days:
        group = [row for d, row in normalized if d == day]
        # Congelar los features de todos los partidos de la fecha antes de
        # incorporar ningún resultado de esa fecha. Evita fuga intradía.
        for match in group:
            h = snapshot(match, "home", day)
            a = snapshot(match, "away", day)
            label = match.get("outcome", "")
            finished = str(match.get("finished", "")).lower() == "true"
            label = label if finished and label in {"H", "D", "A"} else ""
            # Sólo mostrar fixtures futuros con fecha y hora válida.
            timestamp = str(match.get("kickoff_utc", "")).replace("Z", "+00:00")
            kickoff = datetime.fromisoformat(timestamp)
            if kickoff.tzinfo is None:
                kickoff = kickoff.replace(tzinfo=timezone.utc)
            future = not label and kickoff.astimezone(timezone.utc) >= as_of_dt
            output.append({
                "league": match["league"],
                "season_start_year": match["season_start_year"],
                "match_id": match["match_id"],
                "kickoff_utc": match["kickoff_utc"],
                "home_id": match["home_id"], "home_team": match.get("home_team", ""),
                "away_id": match["away_id"], "away_team": match.get("away_team", ""),
                **h, **a,
                "target_1x2": label,
                "future_fixture": future,
                "both_teams_min3_prior": h["home_matches_prev"] >= 3 and a["away_matches_prev"] >= 3,
                "as_of_utc": as_of_dt.isoformat(timespec="seconds"),
                "source": "OpenLigaDB (ODbL 1.0)",
            })
        for match in group:
            # Solo resultados FINALIZADOS y ANTERIORES a la fecha de la
            # consulta pasan al histórico.
            if day >= as_of_dt.date():
                continue
            if str(match.get("finished", "")).lower() != "true":
                continue
            if match.get("outcome") not in {"H", "D", "A"}:
                continue
            try:
                hg = int(match["home_goals"])
                ag = int(match["away_goals"])
            except (ValueError, TypeError, KeyError):
                continue
            for side, gf, ga in (("home", hg, ag), ("away", ag, hg)):
                key = key_for(match, side)
                history[key].append((gf, ga, 3 if gf > ga else (1 if gf == ga else 0), int(gf > ga)))
                last_day[key] = day
    return output


def main():
    root = Path("datasets/actualizados")
    status_file = root / "ultima_actualizacion.json"
    if not status_file.exists():
        raise SystemExit("No hay status de OpenLigaDB. Ejecuta refresh_openligadb.py.")
    metadata = json.loads(status_file.read_text(encoding="utf-8"))
    as_of = metadata["checked_at_utc"]
    out_files = []
    for report in metadata["leagues"]:
        league = report["league"]
        season = report["season"]
        source = root / f"{league}_{season}_partidos.csv"
        if not source.exists():
            raise FileNotFoundError(f"Falta CSV original {source}")
        with source.open(encoding="utf-8", newline="") as file:
            matches = list(csv.DictReader(file))
        if len(matches) != report["matches"]:
            raise ValueError(f"Cantidad de filas no coincide con el manifiesto: {source}")
        result = build_features(matches, as_of)
        if not result:
            raise ValueError(f"Sin partidos para {league}")
        out_files.append((root / f"{league}_{season}_features_prepartido.csv", result))
    for path, rows in out_files:
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(path)
        print(f"{path}: {len(rows)} partidos, {sum(r['future_fixture'] for r in rows)} futuros")
    print("Features calculadas con resultados de fechas anteriores; no representan probabilidades calibradas.")


if __name__ == "__main__":
    main()
