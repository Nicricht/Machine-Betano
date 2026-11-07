#!/usr/bin/env python3
"""Extractor autenticado de eventos deportivos.

API-Football (API-Sports) es un proveedor comercial distinto a OpenLigaDB.
Este script NO inventa xG, ratings EA, lesiones, tiros ni alineaciones.
No ejecuta apuestas. No muestra ni guarda la API key.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://v3.football.api-sports.io"
FINISHED_STATUSES = {"FT", "AET", "PEN"}

FIELDS = {
    "fixtures": [
        "provider", "retrieved_at_utc", "league_id", "season",
        "fixture_id", "kickoff_utc", "status", "home_id", "home_team",
        "away_id", "away_team", "home_goals", "away_goals",
    ],
    "players": [
        "provider", "retrieved_at_utc", "fixture_id", "team_id",
        "player_id", "player", "position", "minutes", "rating",
        "shots_total", "shots_on_target", "goals", "assists",
        "passes_total", "passes_key", "yellow_cards", "red_cards",
    ],
    "team_stats": [
        "provider", "retrieved_at_utc", "fixture_id", "team_id", "team",
        "shots_on_goal", "total_shots", "corner_kicks", "fouls",
        "yellow_cards", "red_cards", "possession",
    ],
    "injuries": [
        "provider", "retrieved_at_utc", "fixture_id", "team_id",
        "player_id", "player", "status", "reason",
    ],
    "lineups": [
        "provider", "retrieved_at_utc", "fixture_id", "team_id",
        "player_id", "player", "role", "position", "formation",
        "collected_before_kickoff",
    ],
}

def obj(value):
    return value if isinstance(value, dict) else {}


def val(value):
    """Preservar nulos como celda vacía, nunca convertirlos a cero."""
    return "" if value is None else value


class QuotaError(RuntimeError):
    pass


class FootballAPI:
    def __init__(self, api_key: str, max_requests: int = 35, reserve: int = 10):
        if not api_key:
            raise ValueError("Se necesita la variable segura API_FOOTBALL_KEY")
        if not 1 <= max_requests <= 100:
            raise ValueError("El presupuesto por ejecución debe estar entre 1 y 100")
        self._key = api_key
        self.budget = max_requests
        self.reserve = reserve
        self.used = 0
        self.remaining = None

    def get(self, route: str, **query):
        if self.used >= self.budget:
            raise QuotaError("Se alcanzó el presupuesto máximo de consultas de esta ejecución")
        if self.remaining is not None and self.remaining <= self.reserve:
            raise QuotaError("Cuota diaria restante demasiado baja; no se consultará más")
        if not route.replace("/", "").replace("-", "").isalpha():
            raise ValueError("Ruta API no permitida")
        url = API_ROOT + "/" + route
        if query:
            url += "?" + urlencode(query)
        request = Request(url, headers={"x-apisports-key": self._key})
        with urlopen(request, timeout=30) as response:
            self.used += 1
            remaining = response.headers.get("x-ratelimit-requests-remaining")
            if remaining is not None:
                self.remaining = int(remaining)
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError("Respuesta de API-Football no es un objeto")
        if payload.get("errors"):
            raise RuntimeError(f"API-Football devolvió errores: {list(obj(payload['errors']))}")
        result = payload.get("response")
        if not isinstance(result, list):
            raise ValueError("Respuesta de API-Football sin lista 'response'")
        pages = obj(payload.get("paging"))
        if pages.get("total", 1) > 1:
            raise ValueError("Respuesta paginada: no se guardarán datos incompletos")
        return result


def normalize_fixtures(items: list[dict], league_id: int, season: int, checked: str):
    rows, fixture_info = [], {}
    seen = set()
    for item in items:
        fixture = obj(item.get("fixture"))
        teams = obj(item.get("teams"))
        goals = obj(item.get("goals"))
        match_id = fixture.get("id")
        status = obj(fixture.get("status")).get("short", "")
        if not isinstance(match_id, int) or match_id in seen:
            raise ValueError("ID de partido inválido o duplicado")
        seen.add(match_id)
        home, away = obj(teams.get("home")), obj(teams.get("away"))
        if not home.get("id") or not away.get("id"):
            raise ValueError("Partido sin identificador de ambos equipos")
        kickoff = fixture.get("date") or ""
        fixture_info[match_id] = kickoff
        finished = status in FINISHED_STATUSES
        rows.append({
            "provider": "API-Football", "retrieved_at_utc": checked,
            "league_id": league_id, "season": season, "fixture_id": match_id,
            "kickoff_utc": kickoff, "status": status,
            "home_id": home.get("id"), "home_team": home.get("name"),
            "away_id": away.get("id"), "away_team": away.get("name"),
            "home_goals": val(goals.get("home")) if finished else "",
            "away_goals": val(goals.get("away")) if finished else "",
        })
    return rows, fixture_info


def normalize_player_stats(items, fixture_id, checked):
    rows = []
    for team_block in items:
        team_id = obj(team_block.get("team")).get("id")
        for player_block in team_block.get("players") or []:
            person = obj(player_block.get("player"))
            for stats in player_block.get("statistics") or []:
                games = obj(stats.get("games"))
                shots = obj(stats.get("shots"))
                goals = obj(stats.get("goals"))
                passes = obj(stats.get("passes"))
                cards = obj(stats.get("cards"))
                rows.append({
                    "provider": "API-Football", "retrieved_at_utc": checked,
                    "fixture_id": fixture_id, "team_id": team_id,
                    "player_id": person.get("id"), "player": person.get("name"),
                    "position": val(games.get("position")),
                    "minutes": val(games.get("minutes")),
                    "rating": val(games.get("rating")),
                    "shots_total": val(shots.get("total")),
                    "shots_on_target": val(shots.get("on")),
                    "goals": val(goals.get("total")),
                    "assists": val(goals.get("assists")),
                    "passes_total": val(passes.get("total")),
                    "passes_key": val(passes.get("key")),
                    "yellow_cards": val(cards.get("yellow")),
                    "red_cards": val(cards.get("red")),
                })
    return rows


def normalize_team_stats(items, fixture_id, checked):
    names = {
        "Shots on Goal": "shots_on_goal",
        "Total Shots": "total_shots",
        "Corner Kicks": "corner_kicks",
        "Fouls": "fouls",
        "Yellow Cards": "yellow_cards",
        "Red Cards": "red_cards",
        "Ball Possession": "possession",
    }
    rows = []
    for team_block in items:
        team = obj(team_block.get("team"))
        metrics = {column: "" for column in names.values()}
        for item in team_block.get("statistics") or []:
            typ = item.get("type")
            if typ in names:
                metrics[names[typ]] = val(item.get("value"))
        rows.append({
            "provider": "API-Football", "retrieved_at_utc": checked,
            "fixture_id": fixture_id, "team_id": team.get("id"),
            "team": team.get("name"), **metrics
        })
    return rows


def normalize_injuries(items, fixture_id, checked):
    rows = []
    for item in items:
        player = obj(item.get("player"))
        team = obj(item.get("team"))
        rows.append({
            "provider": "API-Football", "retrieved_at_utc": checked,
            "fixture_id": fixture_id, "team_id": team.get("id"),
            "player_id": player.get("id"), "player": player.get("name"),
            "status": val(item.get("type")), "reason": val(item.get("reason")),
        })
    return rows


def _parse_utc(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def normalize_lineups(items, fixture_id, checked, kickoff):
    retrieved = _parse_utc(checked)
    kick = _parse_utc(kickoff)
    before = bool(retrieved and kick and retrieved < kick)
    rows = []
    for item in items:
        team = obj(item.get("team"))
        for key, role in (("startXI", "starter"), ("substitutes", "bench")):
            for entry in item.get(key) or []:
                player = obj(entry.get("player"))
                if player.get("id") is None:
                    continue
                rows.append({
                    "provider": "API-Football", "retrieved_at_utc": checked,
                    "fixture_id": fixture_id, "team_id": team.get("id"),
                    "player_id": player.get("id"), "player": player.get("name"),
                    "role": role, "position": val(player.get("pos")),
                    "formation": val(item.get("formation")),
                    "collected_before_kickoff": before,
                })
    return rows


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def collect(client, leagues, season, now, days_back=2, days_ahead=2, recent_limit=3, next_limit=3):
    checked = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    output = {name: [] for name in FIELDS}
    report = {
        "source": "API-Football", "retrieved_at_utc": checked,
        "status": "complete_within_configured_sample",
        "model_ready": False,
        "xg_available": False,
        "ea_ratings_available": False,
        "warning": "Muestra limitada por liga y fecha. Las estadísticas del mismo partido solo existen después de ocurrido; jamás usarlas como features prepartido de ese partido.",
        "leagues": [], "coverage": {},
    }
    from_date = (now - timedelta(days=days_back)).date().isoformat()
    to_date = (now + timedelta(days=days_ahead)).date().isoformat()
    for league_id in leagues:
        fixtures = client.get(
            "fixtures", league=league_id, season=season,
            **{"from": from_date, "to": to_date, "timezone": "UTC"}
        )
        table, kickoff_map = normalize_fixtures(fixtures, league_id, season, checked)
        output["fixtures"].extend(table)
        past = [row for row in table if row["status"] in FINISHED_STATUSES]
        future = [row for row in table if row["status"] not in FINISHED_STATUSES
                  and (_parse_utc(row["kickoff_utc"]) or now) >= now]
        past.sort(key=lambda row: (row["kickoff_utc"], row["fixture_id"]), reverse=True)
        future.sort(key=lambda row: (row["kickoff_utc"], row["fixture_id"]))
        for row in past[:recent_limit]:
            fixture_id = row["fixture_id"]
            output["players"] += normalize_player_stats(
                client.get("fixtures/players", fixture=fixture_id), fixture_id, checked)
            output["team_stats"] += normalize_team_stats(
                client.get("fixtures/statistics", fixture=fixture_id), fixture_id, checked)
        for row in future[:next_limit]:
            fixture_id = row["fixture_id"]
            output["injuries"] += normalize_injuries(
                client.get("injuries", fixture=fixture_id), fixture_id, checked)
            output["lineups"] += normalize_lineups(
                client.get("fixtures/lineups", fixture=fixture_id),
                fixture_id, checked, kickoff_map[fixture_id])
        report["leagues"].append({
            "league_id": league_id, "season": season,
            "fixtures_in_window": len(table),
            "past_fixtures_sampled": min(len(past), recent_limit),
            "future_fixtures_sampled": min(len(future), next_limit),
            "date_from": from_date, "date_to": to_date,
        })
    report["api_calls_used_this_run"] = client.used
    report["api_calls_remaining_provider"] = client.remaining
    report["coverage"] = {name: len(rows) for name, rows in output.items()}
    return output, report


def persist_atomic(output_dir, rows, report):
    """Publicar todos los CSV + metadatos una vez validados.

    En CI se ejecuta en un checkout nuevo. Un error antes de publicar impide
    el commit y conserva el snapshot previo del repositorio.
    """
    if not report["coverage"]["fixtures"]:
        raise ValueError("Sin partidos disponibles en la ventana: no reemplazar snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir.parent) as temporary:
        tmp = Path(temporary)
        for name, fields in FIELDS.items():
            write_csv(tmp / (name + ".csv"), fields, rows[name])
        (tmp / "estado.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for path in tmp.iterdir():
            os.replace(path, output_dir / path.name)


def main():
    parser = argparse.ArgumentParser(description="API-Football: datos avanzados con cuota limitada")
    parser.add_argument("--league", type=int, action="append",
                        help="ID del proveedor. Ej. LaLiga=140, Bundesliga=78")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--budget", type=int, default=35)
    parser.add_argument("--output", type=Path, default=Path("datasets/avanzados"))
    args = parser.parse_args()
    api_key = os.environ.get("API_FOOTBALL_KEY", "")
    if not api_key:
        raise SystemExit("No configurado: falta API_FOOTBALL_KEY. No se hicieron consultas.")
    now = datetime.now(timezone.utc)
    season = args.season or (now.year if now.month >= 7 else now.year - 1)
    client = FootballAPI(api_key, max_requests=args.budget, reserve=10)
    rows, report = collect(client, args.league or [140, 78], season, now)
    persist_atomic(args.output, rows, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
