"""La cobertura de goleadores no debe confundirse con partidos jugados."""
import unittest
from scripts.build_scorer_summary import observed_scorers


def match(h="2", a="1"):
    return {"league": "la1", "season_start_year": "2026", "match_id": "10",
            "home_team": "Local", "away_team": "Visitante",
            "home_goals": h, "away_goals": a}


def goal(pid, name, h, a, penalty=False, own=False):
    return {"league": "la1", "season_start_year": "2026", "match_id": "10",
            "player_id": pid, "player_name": name,
            "home_score_after_goal": str(h), "away_score_after_goal": str(a),
            "is_penalty": str(penalty), "is_own_goal": str(own)}


class ObservedPlayerTests(unittest.TestCase):
    def test_complete_goals_only_no_fictional_minutes(self):
        goals = [goal("7", "Jugador Uno", 1, 0, penalty=True),
                 goal("8", "Jugador Dos", 1, 1),
                 goal("7", "Jugador Uno", 2, 1)]
        rows, report = observed_scorers([match()], goals, "2026-11-07T20:00:00Z")
        scorer = next(r for r in rows if r["openligadb_player_id"] == "7")
        self.assertEqual(scorer["goals_reported"], 2)
        self.assertEqual(scorer["penalty_goals_reported"], 1)
        self.assertEqual(scorer["scoring_matches"], 1)
        self.assertEqual(scorer["games_played_known"], "")
        self.assertEqual(scorer["minutes_known"], "")
        self.assertEqual(scorer["shots_known"], "")
        self.assertFalse(report["all_players_roster_coverage"])

    def test_own_goal_is_not_counted_as_regular_goal(self):
        rows, _ = observed_scorers([match("1", "0")],
            [goal("2", "Jugador Dos", 1, 0, own=True)], "2026-11-07T20:00:00Z")
        self.assertEqual(rows[0]["own_goals_reported"], 1)
        self.assertEqual(rows[0]["goals_reported"], 0)
        self.assertEqual(rows[0]["observed_club"], "Visitante")

    def test_incomplete_goals_do_not_infer_club(self):
        rows, coverage = observed_scorers(
            [match("3", "1")], [goal("1", "Jugador A", 1, 0)],
            "2026-11-07T20:00:00Z")
        self.assertEqual(rows, [])
        self.assertEqual(coverage["goal_events_with_team_inferred"], 0)


if __name__ == "__main__":
    unittest.main()
