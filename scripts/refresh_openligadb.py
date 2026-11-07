#!/usr/bin/env python3
"""Actualización reproducible de resultados y goleadores (OpenLigaDB).

API pública: https://api.openligadb.de
Datos de la comunidad, licencia ODbL 1.0. NO equivalen a estadísticas Opta.
No requiere API key. No ejecuta apuestas ni hace predicciones.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://api.openligadb.de"
MATCH_COLUMNS = [
    "match_id", "league", "season_start_year", "round", "kickoff_utc",
    "home_id", "home_team", "away_id", "away_team", "finished",
    "home_goals", "away_goals", "outcome", "source_last_updated",
    "source", "source_url",
]
GOAL_COLUMNS = [
    "match_id", "league", "season_start_year", "player_id",
    "player_name", "minute", "home_score_after_goal",
    "away_score_after_goal", "is_penalty", "is_own_goal", "source",
]


def season_start(now: datetime) -> int:
    """Temporada europea YYYY/YYYY+1; suele comenzar en mitad de año."""
    return now.year if now.month >= 7 else now.year - 1


def fetch_matches(league: str, season: int, retries: int = 3) -> list[dict]:
    if not league.replace("-", "").isalnum() or len(league) > 12:
        raise ValueError("Identificador de liga no válido")
    if not 2000 <= season <= 2100:
        raise ValueError("Temporada no válida")
    url = f"{BASE}/getmatchdata/{league}/{season}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "Machine-Betano/0.2 (academic-data-refresh)",
            })
            with urlopen(req, timeout=35) as response:
                payload = json.load(response)
            if not isinstance(payload, list) or not payload:
                raise ValueError(f"Fuente vacía o estructura no reconocida: {url}")
            return payload
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Error consultando {url}: {last_error}") from last_error


def final_score(match: dict) -> tuple[int | None, int | None]:
    """Tomar exclusivamente el resultado de 90 minutos (resultTypeID=2)."""
    if not match.get("matchIsFinished"):
        return None, None
    for item in match.get("matchResults") or []:
        if item.get("resultTypeID") == 2:
            home, away = item.get("pointsTeam1"), item.get("pointsTeam2")
            if home is not None and away is not None:
                return int(home), int(away)
    return None, None


def normalize(matches: list[dict], league: str, season: int) -> tuple[list[dict], list[dict]]:
    """Una fila por partido y una por evento goleador; sin datos inventados."""
    if not matches:
        raise ValueError("No hay partidos: no se sobrescribirán datos anteriores")
    seen = set()
    rows, goals = [], []
    for item in matches:
        match_id = item.get("matchID")
        home = item.get("team1") or {}
        away = item.get("team2") or {}
        if not isinstance(match_id, int) or match_id in seen:
            raise ValueError("Match ID inválido o duplicado")
        seen.add(match_id)
        if not home.get("teamName") or not away.get("teamName"):
            raise ValueError(f"Falta un equipo para el partido {match_id}")
        hg, ag = final_score(item)
        outcome = "" if hg is None else ("H" if hg > ag else "A" if hg < ag else "D")
        rows.append({
            "match_id": match_id, "league": league, "season_start_year": season,
            "round": (item.get("group") or {}).get("groupOrderID"),
            "kickoff_utc": item.get("matchDateTimeUTC") or "",
            "home_id": home.get("teamId"),
            "home_team": home["teamName"],
            "away_id": away.get("teamId"),
            "away_team": away["teamName"],
            "finished": bool(item.get("matchIsFinished")),
            "home_goals": hg if hg is not None else "",
            "away_goals": ag if ag is not None else "",
            "outcome": outcome,
            "source_last_updated": item.get("lastUpdateDateTime") or "",
            "source": "OpenLigaDB (comunidad, ODbL-1.0)",
            "source_url": f"{BASE}/getmatchdata/{league}/{season}",
        })
        for goal in item.get("goals") or []:
            if not isinstance(goal, dict):
                continue
            goals.append({
                "match_id": match_id, "league": league,
                "season_start_year": season,
                "player_id": goal.get("goalGetterID") or "",
                "player_name": goal.get("goalGetterName") or "",
                "minute": goal.get("matchMinute") if goal.get("matchMinute") is not None else "",
                "home_score_after_goal": goal.get("scoreTeam1") if goal.get("scoreTeam1") is not None else "",
                "away_score_after_goal": goal.get("scoreTeam2") if goal.get("scoreTeam2") is not None else "",
                "is_penalty": goal.get("isPenalty", ""),
                "is_own_goal": goal.get("isOwnGoal", ""),
                "source": "OpenLigaDB",
            })
    rows.sort(key=lambda r: (r["kickoff_utc"], r["match_id"]))
    goals.sort(key=lambda r: (r["match_id"], str(r["minute"])))
    return rows, goals


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def refresh(leagues: list[str], season: int, out_dir: Path, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    checked = now.isoformat(timespec="seconds")
    report = {
        "checked_at_utc": checked,
        "license": "ODbL-1.0",
        "source": "https://openligadb.de",
        "warning": "Fuente comunitaria. Puede estar retrasada o incompleta; no contiene alineaciones, lesiones, xG ni estadísticas FIFA.",
        "leagues": [],
    }
    # Primero consultar y validar todas las ligas. Un fallo evita publicar
    # una combinación parcial, y la ejecución CI no sube datos fallidos.
    datasets = []
    for league in leagues:
        payload = fetch_matches(league, season)
        rows, goals = normalize(payload, league, season)
        datasets.append((league, rows, goals))
    for league, rows, goals in datasets:
        write_csv(out_dir / f"{league}_{season}_partidos.csv", MATCH_COLUMNS, rows)
        write_csv(out_dir / f"{league}_{season}_goleadores.csv", GOAL_COLUMNS, goals)
        report["leagues"].append({
            "league": league, "season": season,
            "matches": len(rows),
            "finished_with_score": sum(bool(row["outcome"]) for row in rows),
            "missing_final_score": sum(row["finished"] and not row["outcome"] for row in rows),
            "goal_events": len(goals),
            "endpoint": f"{BASE}/getmatchdata/{league}/{season}",
        })
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ultima_actualizacion.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Actualizar resultados desde OpenLigaDB sin API key")
    parser.add_argument("--league", action="append", default=None,
                        help="Código de liga, repetible. Por defecto: la1 y bl1")
    parser.add_argument("--season", type=int, default=None,
                        help="Año de inicio de la temporada, automático por defecto")
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/actualizados"))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    season = args.season if args.season is not None else season_start(now)
    report = refresh(args.league or ["la1", "bl1"], season, args.output_dir, now)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
