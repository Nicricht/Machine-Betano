"""Features sin fuga temporal, construidas desde OpenLigaDB."""
from datetime import datetime, timezone
import unittest

from scripts.build_live_features import build_features


AS_OF = "2026-11-07T15:00:00+00:00"


def match(match_id, day, home, away, hg="", ag="", finished=False, league="la1", season=2026):
    result = "" if not finished else ("H" if hg > ag else "A" if hg < ag else "D")
    return {
        "match_id": str(match_id), "league": league,
        "season_start_year": season, "kickoff_utc": day,
        "home_id": home, "away_id": away,
        "home_team": f"Equipo {home}", "away_team": f"Equipo {away}",
        "finished": str(finished),
        "home_goals": hg, "away_goals": ag,
        "outcome": result,
    }


class PreMatchTests(unittest.TestCase):
    def test_first_match_does_not_know_own_score(self):
        data = [
            match(1, "2026-10-01T14:00:00Z", "1", "2", 5, 0, True),
            match(2, "2026-10-08T14:00:00Z", "2", "1", 0, 1, True),
        ]
        result = build_features(data, AS_OF)
        self.assertEqual(result[0]["home_matches_prev"], 0)
        self.assertEqual(result[0]["home_goals_for_avg5"], "")
        self.assertEqual(result[1]["away_goals_for_avg5"], 5)
        self.assertEqual(result[1]["away_rest_days"], 7)

    def test_same_day_games_do_not_leak(self):
        data = [
            match(1, "2026-10-01T12:00:00Z", "1", "2", 6, 0, True),
            match(2, "2026-10-01T19:00:00Z", "1", "3", 9, 0, True),
            match(3, "2026-10-02T17:00:00Z", "1", "4", 0, 0, True),
        ]
        result = build_features(data, AS_OF)
        self.assertEqual(result[1]["home_matches_prev"], 0)
        self.assertEqual(result[2]["home_goals_for_avg5"], 7.5)

    def test_unplayed_future_has_no_target(self):
        data = [
            match(1, "2026-10-01T12:00:00Z", "1", "2", 2, 0, True),
            match(2, "2026-11-08T12:00:00Z", "2", "1", finished=False),
        ]
        result = build_features(data, AS_OF)
        self.assertEqual(result[1]["target_1x2"], "")
        self.assertTrue(result[1]["future_fixture"])
        self.assertEqual(result[1]["away_goals_for_avg5"], 2)

    def test_no_cross_league_or_season_history(self):
        data = [
            match(1, "2026-01-01T12:00:00Z", "1", "2", 6, 0, True, season=2025),
            match(2, "2026-10-02T12:00:00Z", "1", "2", 0, 1, True, season=2026),
            match(3, "2026-10-03T12:00:00Z", "1", "2", 0, 1, True, league="bl1", season=2026),
        ]
        result = build_features(data, AS_OF)
        self.assertTrue(all(row["home_matches_prev"] == 0 for row in result))

    def test_duplicate_match_ids_rejected(self):
        one = match(1, "2026-10-01T12:00:00Z", "1", "2", 1, 0, True)
        with self.assertRaisesRegex(ValueError, "duplicado"):
            build_features([one, one], AS_OF)

    def test_future_result_claim_never_enters_history(self):
        data = [
            match(1, "2026-11-08T12:00:00Z", "1", "2", 5, 0, True),
            match(2, "2026-11-09T12:00:00Z", "1", "3", finished=False),
        ]
        result = build_features(data, AS_OF)
        self.assertEqual(result[1]["home_matches_prev"], 0)


if __name__ == "__main__":
    unittest.main()
