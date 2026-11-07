"""Pruebas del importador de valoraciones: solo datos sintéticos de test."""
import csv
from pathlib import Path
import tempfile
import unittest

from scripts.import_fc_ratings import FIELDS, import_ratings, validate


def player(**updates):
    row = dict(
        edition="FC27", as_of_date="2026-09-10", fc_player_id="12345",
        name="Futbolista de prueba", club="Club de prueba", position="ST",
        ovr="89", pac="90", sho="85", pas="80", dri="88", phy="77",
        source_url="https://www.ea.com/games/ea-sports-fc/ratings",
    )
    row["def"] = "42"
    row.update(updates)
    return row


class RatingsTests(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(len(validate([player()])), 1)
        self.assertEqual(validate([player(sho="")])[0]["sho"], "")

    def test_bad_ratings_are_rejected(self):
        for value in ["-1", "100", "nan", "fake"]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "sho"):
                validate([player(sho=value)])

    def test_no_duplicate_player_in_same_snapshot(self):
        with self.assertRaisesRegex(ValueError, "duplicado"):
            validate([player(), player()])

    def test_snapshot_distinguishes_versions(self):
        self.assertEqual(len(validate([
            player(), player(as_of_date="2026-10-15"),
            player(edition="FC26", as_of_date="2026-09-10"),
        ])), 3)

    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "source_url"):
            validate([player(source_url="")])

    def test_local_output_not_model_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "input.csv"
            with raw.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow(player())
            status = import_ratings(raw, Path(tmp) / "ratings" / "fc_ratings.csv")
            self.assertEqual(status["records"], 1)
            self.assertEqual(status["identity_matching"], "pending_reviewed_id_mapping")
            self.assertTrue((Path(tmp) / "ratings" / "fc_ratings.csv").exists())


if __name__ == "__main__":
    unittest.main()
