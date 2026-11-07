"""Retroceso de temporada: test con datos inventados, sin llamadas a red."""
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
import unittest

from scripts.historical_backfill import backfill, MIN_COMPLETED, completed_seasons


def game(mid, i, year):
    date = (datetime(year, 8, 1, tzinfo=timezone.utc)+timedelta(days=i)).isoformat()
    score = 2 if i % 3 else 0
    return {
        "matchID": mid,
        "team1": {"teamId": 10+i % 10, "teamName": f"Local {i % 10}"},
        "team2": {"teamId": 30+i % 10, "teamName": f"Visita {i % 10}"},
        "matchDateTimeUTC": date,
        "matchIsFinished": True,
        "matchResults": [{"resultTypeID": 2, "pointsTeam1": score, "pointsTeam2": 1}],
        "goals": [],
    }


class TestHistoricalSource(unittest.TestCase):
    def test_rollover_to_completed_seasons(self):
        self.assertEqual(completed_seasons(datetime(2026, 11, 7, tzinfo=timezone.utc)), (2024, 2025))
        self.assertEqual(completed_seasons(datetime(2027, 8, 1, tzinfo=timezone.utc)), (2025, 2026))
    def test_builds_feature_files_and_recovers_cache(self):
        now = datetime(2026, 11, 7, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "historicos"
            calls = []

            def fake(league, year):
                calls.append((league, year))
                return [game(1000 + i, i, year) for i in range(MIN_COMPLETED+1)] if (
                    league == "la1" and year == 2025) else []

            report = backfill(root, now=now, fetcher=fake)
            self.assertEqual(len(report["leagues"]), 1)
            self.assertEqual(report["leagues"][0]["season"], 2025)
            self.assertEqual(len(report["leagues"][0]["matches_sha256"]), 64)
            self.assertEqual(len(report["leagues"][0]["features_sha256"]), 64)
            self.assertTrue((root / "la1_2025_features_prepartido.csv").exists())
            self.assertTrue((root / "la1_2025_partidos.csv").exists())
            self.assertEqual(len(report["skipped_sources"]), 3)
            # No nuevas consultas cuando hay archivos guardados.
            def should_not_fetch(*_):
                raise AssertionError("No debería volver a consultar datos archivados")
            cached = backfill(root, now=now, fetcher=should_not_fetch)
            self.assertEqual(len(cached["leagues"]), 1)

    def test_no_valid_historical_does_not_write_empty_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "historicos"
            with self.assertRaisesRegex(RuntimeError, "Sin temporadas"):
                backfill(root, fetcher=lambda league, year: [])
            self.assertFalse((root / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
