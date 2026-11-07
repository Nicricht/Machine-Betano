"""Validar que ninguna feature utilice el partido que está prediciendo."""
import unittest

import pandas as pd

from machine_betano.features import build_features
from machine_betano.train import evaluate


def match(mid, day, home, away, gh, ga, season=1):
    return {
        "match_id": mid, "date": day, "competition_id": 37,
        "season_id": season, "home_team_id": home, "away_team_id": away,
        "home_goals": gh, "away_goals": ga,
        "outcome": "H" if gh > ga else ("A" if gh < ga else "D"),
    }


class FeatureTests(unittest.TestCase):
    def test_first_game_never_knows_result(self):
        data = pd.DataFrame([
            match(1, "2020-01-01", 1, 2, 7, 0),
            match(2, "2020-01-08", 2, 1, 0, 1),
        ])
        result = build_features(data)
        self.assertEqual(result.loc[0, "home_matches_prev"], 0)
        self.assertTrue(pd.isna(result.loc[0, "home_gf_avg"]))
        self.assertEqual(result.loc[1, "away_gf_avg"], 7)
        self.assertEqual(result.loc[1, "away_rest_days"], 7)

    def test_same_day_never_leaks(self):
        data = pd.DataFrame([
            match(2, "2020-01-01", 1, 3, 10, 0),
            match(1, "2020-01-01", 1, 2, 8, 0),
            match(3, "2020-01-02", 1, 4, 0, 1),
        ])
        result = build_features(data)
        self.assertEqual(result.loc[0, "home_matches_prev"], 0)
        self.assertEqual(result.loc[1, "home_matches_prev"], 0)
        self.assertEqual(result.loc[2, "home_gf_avg"], 9)

    def test_seasons_isolated(self):
        data = pd.DataFrame([
            match(1, "2020-01-01", 1, 2, 8, 0, season=1),
            match(2, "2021-01-01", 1, 2, 0, 1, season=2),
        ])
        result = build_features(data)
        self.assertEqual(result.loc[1, "home_matches_prev"], 0)

    def test_small_sample_refused(self):
        data = pd.DataFrame([
            match(1, "2020-01-01", 1, 2, 8, 0),
            match(2, "2020-01-08", 1, 2, 1, 0),
        ])
        with self.assertRaisesRegex(ValueError, "mínimo"):
            evaluate(data, __import__("pathlib").Path("outputs/test"), min_rows=80)


if __name__ == "__main__":
    unittest.main()
