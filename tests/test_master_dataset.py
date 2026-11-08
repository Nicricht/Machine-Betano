"""Pruebas del dataset maestro: fuente sintética y nulos correctos."""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_live_features import COLUMNS as FEATURE_COLS, build_features
from scripts.build_master_dataset import (
    build_master, read_csv, validate_one_season, FEATURE_COLUMNS,
    MATCH_COLS, GOAL_COLS,
)


CHECKED = "2026-11-08T09:00:00+00:00"


def game(mid="1", kickoff="2026-10-01T19:00:00Z", finished=True,
         home_goals="1", away_goals="0", outcome="H"):
    return {
        "match_id": mid, "league": "la1", "season_start_year": "2026",
        "kickoff_utc": kickoff, "home_id": "1", "home_team": "Equipo A",
        "away_id": "2", "away_team": "Equipo B",
        "finished": str(finished), "home_goals": home_goals,
        "away_goals": away_goals, "outcome": outcome,
        "source_url": "https://api.openligadb.de/getmatchdata/la1/2026",
    }


def goal():
    return {
        "match_id": "1", "league": "la1", "season_start_year": "2026",
        "player_id": "11", "player_name": "Jugador Uno", "minute": "20",
        "home_score_after_goal": "1", "away_score_after_goal": "0",
        "is_penalty": "False", "is_own_goal": "False",
    }


def make_csv(path: Path, rows, columns=None):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class MasterDatasetTests(unittest.TestCase):
    def setup_source(self, temp: str):
        root = Path(temp)
        current = root / "actualizados"
        hist = root / "historicos"
        dest = root / "maestro"
        current.mkdir()
        hist.mkdir()
        games = [
            game(),
            game("2", "2026-11-11T19:00:00Z", False, "", "", ""),
        ]
        features = build_features(games, CHECKED)
        make_csv(current / "la1_2026_partidos.csv", games)
        make_csv(current / "la1_2026_features_prepartido.csv", features, FEATURE_COLS)
        make_csv(current / "la1_2026_goleadores.csv", [goal()])
        (current / "ultima_actualizacion.json").write_text(json.dumps({
            "checked_at_utc": CHECKED, "license": "ODbL-1.0",
            "leagues": [{"league": "la1", "season": 2026,
                         "matches": 2, "goal_events": 1}],
        }), encoding="utf-8")
        return current, hist, dest, games, features

    def test_build_master_never_trains_and_keeps_postmatch_columns_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            current, hist, dest, _, _ = self.setup_source(temp)
            report = build_master(current, hist, dest)
            self.assertEqual(report["tables"]["master_partidos.csv"], 2)
            self.assertEqual(report["tables"]["master_eventos_gol.csv"], 1)
            self.assertEqual(report["tables"]["master_goleadores_observados.csv"], 1)
            self.assertFalse(report["ready_for_final_player_models"])
            self.assertFalse(report["has_verified_player_shots_minutes_cards"])
            matches = read_csv(dest / "master_partidos.csv")
            self.assertEqual(matches[0]["target_1x2_postmatch"], "H")
            self.assertEqual(matches[1]["target_1x2_postmatch"], "")
            self.assertEqual(matches[1]["home_goals_postmatch"], "")
            self.assertFalse(any("postmatch" in x for x in FEATURE_COLUMNS))
            goal_event = read_csv(dest / "master_eventos_gol.csv")[0]
            self.assertEqual(goal_event["club_inferred"], "Equipo A")
            self.assertEqual(goal_event["event_is_postmatch_only"], "True")
            scorer = read_csv(dest / "master_goleadores_observados.csv")[0]
            self.assertEqual(scorer["minutes_known"], "")
            self.assertEqual(scorer["shots_known"], "")
            self.assertTrue(report["quality_checks_passed"])
            self.assertEqual(len(report["sha256"]["master_partidos.csv"]), 64)

    def test_edited_feature_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, matches, features = self.setup_source(temp)
            features[1]["home_goals_for_avg5"] = "999"
            with self.assertRaisesRegex(ValueError, "inconsistente"):
                validate_one_season(matches, features, CHECKED, label="la1_2026")

    def test_label_cannot_disagree_with_real_score(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, matches, features = self.setup_source(temp)
            matches[0]["home_goals"] = "0"
            with self.assertRaisesRegex(ValueError, "inconsistente|incoherente"):
                validate_one_season(matches, features, CHECKED, label="la1_2026")

    def test_duplicate_match_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, matches, features = self.setup_source(temp)
            with self.assertRaisesRegex(ValueError, "duplicado"):
                validate_one_season(matches + [matches[0]], features, CHECKED,
                                    label="la1_2026")

    def test_missing_goal_events_rejected_by_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            current, hist, dest, _, _ = self.setup_source(temp)
            metadata_path = current / "ultima_actualizacion.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["leagues"][0]["goal_events"] = 2
            metadata_path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "eventos de gol"):
                build_master(current, hist, dest)

    def test_historical_hash_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            current, hist, dest, games, features = self.setup_source(temp)
            prefix = "bl1_2025"
            historical = [dict(g, league="bl1", season_start_year="2025")
                          for g in games[:1]]
            for g in historical:
                g["kickoff_utc"] = "2025-10-01T19:00:00Z"
            hist_features = build_features(historical, CHECKED)
            make_csv(hist / (prefix + "_partidos.csv"), historical)
            make_csv(hist / (prefix + "_features_prepartido.csv"),
                     hist_features, FEATURE_COLS)
            (hist / "manifest.json").write_text(json.dumps({
                "license": "ODbL-1.0", "checked_at_utc": CHECKED,
                "leagues": [{
                    "league": "bl1", "season": 2025, "matches": 1,
                    "matches_sha256": "0"*64,
                }],
            }))
            with self.assertRaisesRegex(ValueError, "Checksum"):
                build_master(current, hist, dest)


if __name__ == "__main__":
    unittest.main()
