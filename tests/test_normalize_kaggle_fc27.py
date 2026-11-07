"""Pruebas sintéticas del convertidor Kaggle FC27 -> esquema interno."""
from pathlib import Path
import tempfile
import unittest

from scripts.normalize_kaggle_fc27 import normalize_csv


class NormalizeFC27Tests(unittest.TestCase):
    def data(self, folder, content):
        path = Path(folder) / "players.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_complete_row_and_snapshot_date(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.data(t, "player_id,first_name,last_name,common_name,overall_rating,club,position,pace,shooting,passing,dribbling,defending,physicality,edition,snapshot_date\n123,Jugador,Uno,,88,Equipo,ST,91,89,77,87,38,79,fc27,2026-09-12\n")
            out = Path(t) / "private" / "fc_ratings.csv"
            result = normalize_csv(p, out)
            self.assertEqual(result["records"], 1)
            self.assertIn("FC27,2026-09-12,123,Jugador Uno,Equipo,ST,88,91,89,77,87,38,79", out.read_text())
            self.assertFalse(result["copyright_license_cleared"])

    def test_reject_missing_snapshot_date(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.data(t, "player_id,name,overall_rating,club,position\n123,A,88,Equipo,ST\n")
            with self.assertRaisesRegex(ValueError, "snapshot_date"):
                normalize_csv(p, Path(t) / "output.csv")

    def test_reject_future_editions(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.data(t, "player_id,name,overall_rating,club,position,edition,snapshot_date\n123,A,88,Equipo,ST,fc26,2026-09-12\n")
            with self.assertRaisesRegex(ValueError, "edición inesperada"):
                normalize_csv(p, Path(t) / "output.csv")

    def test_no_synthetic_zero_for_missing_attributes(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.data(t, "player_id,name,overall_rating,club,position,edition,snapshot_date,pace\n123,A,88,Equipo,GK,fc27,2026-09-12,\n")
            out = Path(t) / "output.csv"
            normalize_csv(p, out)
            self.assertIn("FC27,2026-09-12,123,A,Equipo,GK,88,,,,,,,", out.read_text())


if __name__ == "__main__":
    unittest.main()
