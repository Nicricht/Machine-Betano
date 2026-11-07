"""Pruebas aisladas sin descargar datos externos."""
import unittest

from machine_betano.statsbomb import matches_table, player_shots_table


class DataTests(unittest.TestCase):
    def test_match_outcome(self):
        matches = [{
            "match_id": 7, "match_date": "2020-02-01",
            "home_team": {"home_team_id": 1, "home_team_name": "Equipo A"},
            "away_team": {"away_team_id": 2, "away_team_name": "Equipo B"},
            "home_score": 2, "away_score": 2,
        }]
        df = matches_table(matches, 37, 90)
        self.assertEqual(df.loc[0, "outcome"], "D")
        self.assertEqual(df.loc[0, "source"], "StatsBomb Open Data")

    def test_player_events_summary(self):
        events = [{
            "type": {"name": "Shot"},
            "player": {"id": 5, "name": "Jugadora 5"},
            "team": {"id": 1, "name": "Equipo A"},
            "shot": {"statsbomb_xg": 0.35, "outcome": {"name": "Goal"}},
        }, {
            "type": {"name": "Shot"},
            "player": {"id": 5, "name": "Jugadora 5"},
            "team": {"id": 1, "name": "Equipo A"},
            "shot": {"statsbomb_xg": 0.15, "outcome": {"name": "Off T"}},
        }]
        df = player_shots_table({10: events})
        self.assertEqual(int(df.loc[0, "shots"]), 2)
        self.assertEqual(int(df.loc[0, "goals_from_shots"]), 1)
        self.assertAlmostEqual(df.loc[0, "shot_xg"], 0.5)


if __name__ == "__main__":
    unittest.main()
