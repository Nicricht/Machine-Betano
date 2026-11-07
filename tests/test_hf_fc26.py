"""Pruebas de auditoría con CSV ficticios: sin descarga ni ratings de EA."""
import unittest

from scripts.audit_hf_fc26 import audit_csv, audit_sources


def csv_bytes(rows, goalkeeper=False):
    if goalkeeper:
        columns = "id,overallRating,firstName,lastName,team,position,gkDiving,gkHandling,gkKicking,gkPositioning,gkReflexes"
    else:
        columns = "id,overallRating,firstName,lastName,team,position,pac,sho,pas,dri,def,phy"
    return (columns + "\n" + "\n".join(rows) + "\n").encode("utf-8")


class HuggingFaceDataTests(unittest.TestCase):
    def test_outfield_and_gk_have_different_schemas(self):
        players = csv_bytes(["1,88,Jugador,Uno,Club A,ST,92,85,73,88,24,79"])
        keepers = csv_bytes(["2,86,Portero,Dos,Club B,GK,87,84,79,86,85"], True)
        result = audit_sources(players, keepers, "2026-11-07T16:00:00Z")
        self.assertEqual(result["total_rows"], 2)
        self.assertFalse(result["training_ready"])
        self.assertEqual(result["tables"][1]["overall_min"], 86)
        self.assertEqual(result["license"], "NO_VERIFICADA")

    def test_duplicate_ids_fail(self):
        row = "1,88,Jugador,Uno,Club A,ST,92,85,73,88,24,79"
        with self.assertRaisesRegex(ValueError, "repetido"):
            audit_csv(csv_bytes([row, row]), "outfield")

    def test_out_of_range_rating_fails(self):
        with self.assertRaisesRegex(ValueError, "sho"):
            audit_csv(csv_bytes(["1,88,Jugador,Uno,Club A,ST,92,200,73,88,24,79"]), "outfield")

    def test_unknown_schema_fails(self):
        with self.assertRaisesRegex(ValueError, "Faltan columnas"):
            audit_csv(b"id,overallRating\n1,88\n", "goalkeepers")

    def test_missing_club_is_counted_not_faked(self):
        result = audit_csv(csv_bytes(["1,88,Jugador,Uno,,ST,92,85,73,88,24,79"]), "outfield")
        self.assertEqual(result["missing_club"], 1)

    def test_empty_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "sin jugadores"):
            audit_csv(csv_bytes([]), "outfield")


if __name__ == "__main__":
    unittest.main()
