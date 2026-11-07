"""Pruebas aisladas del auditor FC27; solo futbolistas ficticios."""
import tempfile
from pathlib import Path
import unittest

from scripts.audit_kaggle_fc27 import inspect_csv, inspect_directory, schema_map


class FC27AuditTests(unittest.TestCase):
    def sample(self, directory, body, name="fc27.csv"):
        path = Path(directory) / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_standard_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.sample(temp, "player_id,name,club,position,overall_rating,pace,shooting,passing,dribbling,defending,physicality\n1,Jugador A,Club A,ST,89,92,85,72,87,20,82\n2,Jugador B,Club B,GK,80,,,,,,\n")
            r = inspect_csv(p)
            self.assertEqual(r["rows"], 2)
            self.assertEqual(r["columns"], 11)
            self.assertEqual(r["mapped_core_columns"]["ovr"], "overall_rating")
            self.assertEqual(r["nonempty_core_fields"]["pac"], 1)
            report = inspect_directory(Path(temp), "2026-11-07T00:00:00Z")
            self.assertFalse(report["license_verified"])
            self.assertFalse(report["ready_to_join_players"])
            self.assertEqual(report["candidate_csv"][0]["rows"], 2)

    def test_first_last_only(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.sample(temp, "id,first_name,last_name,team,position,ovr,pac\n1,Nombre,Apellido,Club,CM,77,64\n")
            self.assertEqual(inspect_csv(p)["missing_name"], 0)

    def test_duplicate_id_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.sample(temp, "id,name,overall\n1,A,70\n1,B,69\n")
            with self.assertRaisesRegex(ValueError, "duplicado"):
                inspect_csv(p)

    def test_out_of_bounds_rating(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.sample(temp, "id,name,overall,pace\n1,A,70,102\n")
            with self.assertRaisesRegex(ValueError, "pac fuera"):
                inspect_csv(p)

    def test_reject_unknown_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            self.sample(temp, "foo,bar\n1,2\n")
            with self.assertRaisesRegex(ValueError, "Ningún CSV"):
                inspect_directory(Path(temp))

    def test_alternative_aliases(self):
        mapped = schema_map(["EA ID", "Display Name", "Overall", "Club Name", "Pace"])
        self.assertEqual(mapped["fc_player_id"], "EA ID")
        self.assertEqual(mapped["name"], "Display Name")
        self.assertEqual(mapped["club"], "Club Name")


if __name__ == "__main__":
    unittest.main()
