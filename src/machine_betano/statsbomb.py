"""Acceso de lectura a StatsBomb Open Data y normalización básica.

Fuente: https://github.com/hudl/open-data
No inferir cobertura completa, y atribuir a StatsBomb al publicar resultados.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = "https://raw.githubusercontent.com/hudl/open-data/master/data"


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "Machine-Betano-educational/0.1"
    return session


def download_json(path: str, session: requests.Session | None = None) -> list[dict]:
    """Descargar JSON público; los errores HTTP no se silencian."""
    if ".." in path or path.startswith("/"):
        raise ValueError("Ruta remota no válida")
    client = session or _session()
    response = client.get(f"{ROOT}/{path}", timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Se esperaba un array JSON de StatsBomb")
    return payload


def catalog_table(competitions: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "competition_id": c["competition_id"],
            "season_id": c["season_id"],
            "country": c.get("country_name"),
            "competition": c.get("competition_name"),
            "season": c.get("season_name"),
            "gender": c.get("competition_gender"),
        }
        for c in competitions
    ])


def matches_table(matches: list[dict], competition_id: int, season_id: int) -> pd.DataFrame:
    rows = []
    for m in matches:
        home_goals = m.get("home_score")
        away_goals = m.get("away_score")
        if home_goals is None or away_goals is None:
            continue
        home_goals, away_goals = int(home_goals), int(away_goals)
        outcome = "H" if home_goals > away_goals else ("A" if home_goals < away_goals else "D")
        rows.append({
            "match_id": int(m["match_id"]),
            "date": str(m["match_date"]),
            "kick_off": m.get("kick_off"),
            "competition_id": int(competition_id),
            "season_id": int(season_id),
            "home_team_id": int(m["home_team"]["home_team_id"]),
            "home_team": m["home_team"]["home_team_name"],
            "away_team_id": int(m["away_team"]["away_team_id"]),
            "away_team": m["away_team"]["away_team_name"],
            "home_goals": home_goals,
            "away_goals": away_goals,
            "outcome": outcome,
            "source": "StatsBomb Open Data",
        })
    if not rows:
        raise ValueError("No se encontraron partidos con marcador")
    df = pd.DataFrame(rows).sort_values(["date", "match_id"]).reset_index(drop=True)
    if df["match_id"].duplicated().any():
        raise ValueError("IDs de partidos duplicados en la fuente")
    return df


def player_shots_table(events_by_match: dict[int, list[dict]]) -> pd.DataFrame:
    """Resumen DESCRIPTIVO posterior al partido, nunca features del mismo encuentro."""
    counts: dict[tuple[int, int], dict] = {}
    for match_id, events in events_by_match.items():
        for event in events:
            if (event.get("type") or {}).get("name") != "Shot":
                continue
            player = event.get("player") or {}
            team = event.get("team") or {}
            if "id" not in player or "id" not in team:
                continue
            key = (int(match_id), int(player["id"]))
            if key not in counts:
                counts[key] = {
                    "match_id": int(match_id),
                    "player_id": int(player["id"]),
                    "player": player.get("name"),
                    "team_id": int(team["id"]),
                    "team": team.get("name"),
                    "shots": 0,
                    "goals_from_shots": 0,
                    "shot_xg": 0.0,
                }
            shot = event.get("shot") or {}
            row = counts[key]
            row["shots"] += 1
            row["shot_xg"] += float(shot.get("statsbomb_xg") or 0)
            if (shot.get("outcome") or {}).get("name") == "Goal":
                row["goals_from_shots"] += 1
    return pd.DataFrame(list(counts.values()), columns=[
        "match_id", "player_id", "player", "team_id", "team",
        "shots", "goals_from_shots", "shot_xg",
    ])


def fetch_season(competition_id: int, season_id: int, root: Path, events_limit: int = 0) -> tuple[Path, Path | None]:
    """Guardar partidos y opcionalmente un subconjunto explícito de eventos."""
    if events_limit < 0:
        raise ValueError("events_limit no puede ser negativo")
    raw_dir = root / "raw" / "statsbomb"
    processed_dir = root / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{competition_id}_{season_id}"
    raw_matches = download_json(f"matches/{competition_id}/{season_id}.json")
    (raw_dir / f"matches_{stem}.json").write_text(
        json.dumps(raw_matches, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    matches = matches_table(raw_matches, competition_id, season_id)
    matches_path = processed_dir / f"matches_{stem}.csv"
    matches.to_csv(matches_path, index=False)
    player_path = None
    if events_limit:
        event_map = {}
        for match_id in matches["match_id"].head(events_limit):
            event_map[int(match_id)] = download_json(f"events/{int(match_id)}.json")
        players = player_shots_table(event_map)
        player_path = processed_dir / f"player_shots_sample_{stem}.csv"
        players.to_csv(player_path, index=False)
        (processed_dir / f"player_shots_sample_{stem}_metadata.json").write_text(
            json.dumps({
                "source": "StatsBomb Open Data",
                "sample_matches": len(event_map),
                "total_matches": len(matches),
                "partial": len(event_map) < len(matches),
                "description": "Tiros, goles provenientes de tiros y xG posteriores al encuentro; no sirve como feature prepartido del mismo encuentro.",
            }, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return matches_path, player_path
