"""Features calculadas ANTES del partido; protecciones contra fuga temporal."""
from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd

FEATURE_COLUMNS = [
    "home_matches_prev", "home_gf_avg", "home_ga_avg",
    "home_points_avg", "home_win_rate", "home_rest_days",
    "away_matches_prev", "away_gf_avg", "away_ga_avg",
    "away_points_avg", "away_win_rate", "away_rest_days",
]


def build_features(matches: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    if window < 1:
        raise ValueError("window debe ser positivo")
    required = {
        "match_id", "date", "competition_id", "season_id", "home_team_id",
        "away_team_id", "home_goals", "away_goals", "outcome",
    }
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"Faltan columnas: {sorted(missing)}")
    if matches["match_id"].duplicated().any():
        raise ValueError("IDs de partidos duplicados")
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    df = df.sort_values(["date", "match_id"]).reset_index(drop=True)
    history = defaultdict(lambda: deque(maxlen=window))
    last_date: dict[tuple[int, int, int], pd.Timestamp] = {}
    output = []

    def key(row: pd.Series, side: str) -> tuple[int, int, int]:
        return (int(row["competition_id"]), int(row["season_id"]), int(row[f"{side}_team_id"]))

    def snapshot(team_key: tuple[int, int, int], day: pd.Timestamp, prefix: str) -> dict:
        recent = history[team_key]
        n = len(recent)
        last = last_date.get(team_key)
        result = {
            f"{prefix}_matches_prev": n,
            f"{prefix}_rest_days": (day - last).days if last is not None else None,
        }
        for name, index in [("gf_avg", 0), ("ga_avg", 1), ("points_avg", 2), ("win_rate", 3)]:
            result[f"{prefix}_{name}"] = sum(r[index] for r in recent) / n if n else None
        return result

    # Se procesan todos los encuentros de una misma fecha ANTES de actualizar
    # históricos, incluso si la fuente cambia el orden de los partidos.
    for day, group in df.groupby("date", sort=True):
        for _, row in group.iterrows():
            record = row.to_dict()
            record.update(snapshot(key(row, "home"), day, "home"))
            record.update(snapshot(key(row, "away"), day, "away"))
            record["date"] = day.strftime("%Y-%m-%d")
            output.append(record)
        for _, row in group.iterrows():
            hg, ag = int(row["home_goals"]), int(row["away_goals"])
            home_key, away_key = key(row, "home"), key(row, "away")
            history[home_key].append((hg, ag, 3 if hg > ag else (1 if hg == ag else 0), int(hg > ag)))
            history[away_key].append((ag, hg, 3 if ag > hg else (1 if hg == ag else 0), int(ag > hg)))
            last_date[home_key] = day
            last_date[away_key] = day
    return pd.DataFrame(output)
