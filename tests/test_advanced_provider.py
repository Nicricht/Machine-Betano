"""API-Football: pruebas locales sin credenciales y sin llamadas externas."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts.refresh_api_football import (
    FootballAPI, QuotaError, collect, normalize_fixtures,
    normalize_injuries, normalize_lineups, normalize_player_stats,
    normalize_team_stats, persist_atomic,
)

CHECKED = "2026-11-07T15:00:00+00:00"


def fixture(fid, timestamp, status, home_score=None, away_score=None):
    return {
        "fixture": {"id": fid, "date": timestamp, "status": {"short": status}},
        "teams": {
            "home": {"id": 10, "name": "Equipo A"},
            "away": {"id": 20, "name": "Equipo B"},
        },
        "goals": {"home": home_score, "away": away_score},
    }


class FakeClient:
    def __init__(self):
        self.used = 0
        self.remaining = 78

    def get(self, route, **params):
        self.used += 1
        if route == "fixtures":
            return [
                fixture(101, "2026-11-05T20:00:00+00:00", "FT", 2, 1),
                fixture(102, "2026-11-08T20:00:00+00:00", "NS", None, None),
            ]
        if route == "fixtures/players":
            return [{"team": {"id": 10}, "players": [{
                "player": {"id": 4, "name": "Delantero"},
                "statistics": [{
                    "games": {"minutes": 83, "position": "Attacker", "rating": "7.4"},
                    "shots": {"total": 3, "on": 1},
                    "goals": {"total": 1, "assists": None},
                    "passes": {"total": 20, "key": 2},
                    "cards": {"yellow": 0, "red": 0},
                }]
            }]}]
        if route == "fixtures/statistics":
            return [{"team": {"id": 10, "name": "Equipo A"},
                     "statistics": [
                         {"type": "Shots on Goal", "value": 4},
                         {"type": "Corner Kicks", "value": 7},
                         {"type": "Ball Possession", "value": "61%"},
                     ]}]
        if route == "injuries":
            return [{"player": {"id": 8, "name": "Defensor"},
                     "team": {"id": 20}, "type": "Missing Fixture",
                     "reason": "Injured"}]
        if route == "fixtures/lineups":
            return [{"team": {"id": 10}, "formation": "4-3-3",
                     "startXI": [{"player": {"id": 4, "name": "Delantero", "pos": "F"}}],
                     "substitutes": [{"player": {"id": 5, "name": "Suplente", "pos": "M"}}]}]
        raise AssertionError(f"Ruta inesperada: {route}")


class AdvancedDataTests(unittest.TestCase):
    def test_not_faking_unplayed_score(self):
        rows, _ = normalize_fixtures([
            fixture(1, "2026-11-09T20:00:00Z", "NS", 3, 0),
            fixture(2, "2026-11-01T20:00:00Z", "AET", 2, 1),
            fixture(3, "2026-11-02T20:00:00Z", "FT", 1, 0),
        ], 140, 2026, CHECKED)
        self.assertEqual(rows[0]["home_goals"], "")
        self.assertEqual(rows[1]["home_goals"], "")
        self.assertEqual(rows[2]["home_goals"], 1)

    def test_missing_statistics_remain_unknown(self):
        stats = normalize_team_stats([
            {"team": {"id": 10, "name": "Local"},
             "statistics": [{"type": "Corner Kicks", "value": 6}]}
        ], 5, CHECKED)
        self.assertEqual(stats[0]["corner_kicks"], 6)
        self.assertEqual(stats[0]["shots_on_goal"], "")
        players = normalize_player_stats([{
            "team": {"id": 10}, "players": [
                {"player": {"id": 99, "name": "Sin tiros"},
                 "statistics": [{"games": {"minutes": 45}, "shots": {"on": None}}]}
            ]}], 5, CHECKED)
        self.assertEqual(players[0]["shots_on_target"], "")
        self.assertEqual(players[0]["minutes"], 45)

    def test_lineup_has_pre_kickoff_flag(self):
        lineup = FakeClient().get("fixtures/lineups")
        before = normalize_lineups(lineup, 102, CHECKED, "2026-11-08T20:00:00Z")
        after = normalize_lineups(lineup, 102, CHECKED, "2026-11-06T20:00:00Z")
        self.assertEqual(len(before), 2)
        self.assertTrue(all(row["collected_before_kickoff"] for row in before))
        self.assertTrue(all(not row["collected_before_kickoff"] for row in after))

    def test_missing_key_and_quota_enforced(self):
        with self.assertRaises(ValueError):
            FootballAPI("")
        client = FootballAPI("fake-key", max_requests=1)
        client.used = 1
        with self.assertRaises(QuotaError):
            client.get("fixtures", league=140)
        client.used = 0
        client.remaining = 10
        with self.assertRaises(QuotaError):
            client.get("fixtures", league=140)

    def test_end_to_end_normalization_and_csv(self):
        now = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)
        rows, report = collect(FakeClient(), [140], 2026, now)
        self.assertEqual(report["coverage"]["fixtures"], 2)
        self.assertEqual(report["coverage"]["players"], 1)
        self.assertEqual(report["coverage"]["team_stats"], 1)
        self.assertEqual(report["coverage"]["injuries"], 1)
        self.assertEqual(report["coverage"]["lineups"], 2)
        self.assertEqual(report["api_calls_used_this_run"], 5)
        self.assertFalse(report["xg_available"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "avanzados"
            persist_atomic(path, rows, report)
            self.assertEqual(len(list(path.glob("*.csv"))), 5)
            status = json.loads((path / "estado.json").read_text(encoding="utf-8"))
            self.assertFalse(status["model_ready"])
            self.assertIn("provider", (path / "fixtures.csv").read_text())

    def test_empty_fixture_window_preserves_previous_snapshot(self):
        client = FakeClient()
        old = client.get
        client.get = lambda route, **params: [] if route == "fixtures" else old(route, **params)
        now = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)
        rows, report = collect(client, [140], 2026, now)
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "avanzados"
            dest.mkdir()
            sentinel = dest / "estado.json"
            sentinel.write_text("antiguo", encoding="utf-8")
            with self.assertRaises(ValueError):
                persist_atomic(dest, rows, report)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "antiguo")


if __name__ == "__main__":
    unittest.main()
