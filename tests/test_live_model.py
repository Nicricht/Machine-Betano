"""Pruebas sin red para evaluacion temporal y calidad de probabilidades."""
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path
import csv
import json
import unittest

import numpy as np
from scripts.build_live_features import FEATURES
from scripts.train_live_1x2 import (
    LABELS, X_COLS, baseline, evaluate, fit_report, matrix,
    read_rows, run, split_temporally, utc,
)


CHECKED = "2026-11-07T20:00:00+00:00"


def row(i: int, *, future=False):
    date = datetime(2026, 8, 15, tzinfo=timezone.utc) + timedelta(days=i)
    if future:
        date = datetime(2026, 11, 8, tzinfo=timezone.utc)
    result = "" if future else LABELS[i % 3]
    data = {
        "league": "la1", "season_start_year": "2026",
        "match_id": str(i), "kickoff_utc": date.isoformat(),
        "home_team": "Local", "away_team": "Visita",
        "target_1x2": result, "future_fixture": str(future),
        "both_teams_min3_prior": "True",
        "as_of_utc": CHECKED, "source": "OpenLigaDB",
    }
    for k, field in enumerate(X_COLS):
        data[field] = str(2 + ((i + k) % 4))
    return data


class TestTemporalModel(unittest.TestCase):
    def test_split_never_shares_date(self):
        values = [row(i) for i in range(70)]
        for x in values:
            x["_kickoff"] = utc(x["kickoff_utc"])
        train, test = split_temporally(values)
        self.assertTrue(max(x["_kickoff"].date() for x in train) <
                        min(x["_kickoff"].date() for x in test))
        self.assertGreater(len(test), 10)

    def test_baseline_depends_only_on_train(self):
        prediction = baseline(["H", "H", "H", "D"], 3)
        self.assertAlmostEqual(float(prediction[0].sum()), 1)
        self.assertGreater(prediction[0, 0], prediction[0, 2])
        self.assertTrue(np.array_equal(prediction[0], prediction[2]))

    def test_accuracy_brier_and_log_loss(self):
        values = np.asarray([[0.6, 0.2, 0.2], [0.3, 0.6, 0.1]])
        m = evaluate(["H", "D"], values)
        self.assertEqual(m["accuracy"], 1.0)
        self.assertGreater(m["log_loss"], 0)
        self.assertGreater(m["brier_multiclass"], 0)

    def test_model_scores_upcoming_only_with_history(self):
        values = [row(i) for i in range(70)]
        values += [row(900, future=True)]
        for x in values:
            x["_kickoff"] = utc(x["kickoff_utc"])
        report, predictions = fit_report(values, CHECKED)
        self.assertEqual(report["upcoming_next_7_days_with_enough_history"], 1)
        if report["test_model_better_log_loss_than_baseline"]:
            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0]["match_id"], "900")
            self.assertAlmostEqual(
                sum(predictions[0][x] for x in ("p_home", "p_draw", "p_away")), 1, places=4
            )
        else:
            self.assertEqual(predictions, [])
            self.assertEqual(report["publication_guard"], "BLOCKED_MODEL_WORSE_THAN_BASELINE")
        self.assertFalse(report["player_ratings_in_training"])
        self.assertIn("baseline_only_train_distribution", report)
        self.assertLess(report["train_end_utc"], report["test_start_utc"])

    def test_no_future_label_in_manifest(self):
        values = [row(800, future=True)]
        values[0]["target_1x2"] = "H"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (root / "la1_2026_features_prepartido.csv").open(
                    "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
            with self.assertRaisesRegex(ValueError, "futuro"):
                read_rows(root, {"checked_at_utc": CHECKED,
                                 "leagues": [{"league": "la1", "season": 2026, "matches": 1}]})

    def test_unequal_snapshot_date_aborts(self):
        values = [row(0)]
        values[0]["as_of_utc"] = "2026-11-06T20:00:00Z"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (root / "la1_2026_features_prepartido.csv").open(
                    "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
            with self.assertRaisesRegex(ValueError, "desactualizadas"):
                read_rows(root, {"checked_at_utc": CHECKED,
                                 "leagues": [{"league": "la1", "season": 2026, "matches": 1}]})

    def test_csv_result_does_not_require_fifa_api(self):
        values = [row(i) for i in range(70)] + [row(999, future=True)]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / "data"
            data.mkdir()
            (data / "ultima_actualizacion.json").write_text(
                json.dumps({"checked_at_utc": CHECKED,
                    "leagues": [{"league": "la1", "season": 2026, "matches": len(values)}]}),
                encoding="utf-8")
            with (data / "la1_2026_features_prepartido.csv").open(
                    "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
            report = run(data, root / "model")
            self.assertEqual(report["upcoming_next_7_days_with_enough_history"], 1)
            self.assertTrue((root / "model" / "modelo_1x2_validacion.json").exists())
            self.assertTrue((root / "model" / "partidos_proximos_1x2_exploratorio.csv").exists())


if __name__ == "__main__":
    unittest.main()
