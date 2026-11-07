"""Pruebas sin red: fuentes vacías, resultados futuros y goleadores."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_openligadb import (
    final_score, normalize, refresh, season_start,
)


def game(mid=1, finished=True):
    return {
        "matchID": mid, "leagueShortcut": "la1", "leagueSeason": 2026,
        "team1": {"teamId": 10, "teamName": "Local"},
        "team2": {"teamId": 20, "teamName": "Visitante"},
        "group": {"groupOrderID": 5},
        "matchDateTimeUTC": "2026-11-07T19:00:00Z",
        "matchIsFinished": finished,
        "matchResults": [
            {"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
            {"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1},
        ],
        "goals": [{
            "goalGetterID": 99, "goalGetterName": "Jugador prueba",
            "matchMinute": 67, "scoreTeam1": 2, "scoreTeam2": 1,
            "isPenalty": False, "isOwnGoal": False,
        }],
    }


class LiveRefreshTests(unittest.TestCase):
    def test_season_rollover(self):
        self.assertEqual(season_start(datetime(2026, 11, 7, tzinfo=timezone.utc)), 2026)
        self.assertEqual(season_start(datetime(2027, 3, 1, tzinfo=timezone.utc)), 2026)

    def test_ignore_halftime_and_upcoming(self):
        self.assertEqual(final_score(game()), (2, 1))
        self.assertEqual(final_score(game(finished=False)), (None, None))
        partial = game()
        partial["matchResults"] = [{"resultTypeID": 1, "pointsTeam1": 2, "pointsTeam2": 0}]
        self.assertEqual(final_score(partial), (None, None))

    def test_normalize_unplayed_does_not_invent_score(self):
        rows, goals = normalize([game(finished=False)], "la1", 2026)
        self.assertEqual(rows[0]["outcome"], "")
        self.assertEqual(rows[0]["home_goals"], "")
        self.assertEqual(goals[0]["player_name"], "Jugador prueba")

    def test_reject_bad_source_before_overwrite(self):
        with self.assertRaises(ValueError):
            normalize([], "la1", 2026)
        with self.assertRaises(ValueError):
            normalize([game(), game()], "la1", 2026)

    def test_refresh_produces_csv_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("scripts.refresh_openligadb.fetch_matches", return_value=[game()]):
                output = refresh(["la1"], 2026, Path(td),
                                 datetime(2026, 11, 7, tzinfo=timezone.utc))
            self.assertEqual(output["leagues"][0]["matches"], 1)
            self.assertTrue((Path(td) / "la1_2026_partidos.csv").exists())
            self.assertTrue((Path(td) / "la1_2026_goleadores.csv").exists())
            self.assertTrue((Path(td) / "ultima_actualizacion.json").exists())


if __name__ == "__main__":
    unittest.main()
