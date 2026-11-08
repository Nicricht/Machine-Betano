"""Test de enriquecimiento FIFA con tablas privadas y mapas revisados."""
from pathlib import Path
import csv
import tempfile
import unittest

from scripts.enrich_master_fc27 import integrate


def write(path, records):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def player(pid="123", name="Jugador A"):
    return {
        "fc_player_id": pid, "edition": "FC27", "as_of_date": "2026-09-12",
        "name": name, "club": "Equipo A", "position": "ST",
        "ovr": "88", "pac": "93", "sho": "90", "pas": "67",
        "dri": "70", "def": "22", "phy": "82", "source_url": "https://example.org/",
    }


def scorer(pid="55", name="J. A"):
    return {
        "league": "la1", "season_start_year": "2026",
        "openligadb_player_id": pid, "openligadb_player_name": name,
        "observed_club": "Equipo A", "scoring_matches": "2",
        "goals_reported": "3",
    }


def mapping(pid="55", fc_id="123"):
    return {
        "league": "la1", "openligadb_player_id": pid,
        "fc_player_id": fc_id, "review_status": "VERIFIED",
        "reviewed_by": "Revisor independiente",
        "reviewed_on": "2026-11-08",
        "evidence_url": "https://example.org/identity",
    }


class MasterFC27Tests(unittest.TestCase):
    def prepare(self, dir):
        root = Path(dir)
        fifa, ol, registry = root / "ratings.csv", root / "scorers.csv", root / "map.csv"
        write(fifa, [player()])
        write(ol, [scorer()])
        return root, fifa, ol, registry

    def test_no_registry_means_no_fake_identity(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            report = integrate(fifa, ol, registry, root / "private")
            self.assertEqual(report["fc27_catalog_rows"], 1)
            self.assertEqual(report["linked_scorer_rows"], 0)
            self.assertFalse(report["ready_for_player_match_training"])
            rows = list(csv.DictReader((root / "private/master_fc27_jugadores_verificados.csv").open()))
            self.assertEqual(rows[0]["ovr"], "")
            self.assertEqual(rows[0]["identity_status"], "UNLINKED")

    def test_verified_mapping_populates_rating_without_name_matching(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            write(registry, [mapping()])
            report = integrate(fifa, ol, registry, root / "private")
            self.assertEqual(report["linked_scorer_rows"], 1)
            rows = list(csv.DictReader((root / "private/master_fc27_jugadores_verificados.csv").open()))
            self.assertEqual(rows[0]["ovr"], "88")
            self.assertEqual(rows[0]["fc_player_id_verified"], "123")

    def test_missing_verification_is_rejected(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            write(registry, [dict(mapping(), review_status="PROVISIONAL_EXACT")])
            with self.assertRaisesRegex(ValueError, "VERIFIED"):
                integrate(fifa, ol, registry, root / "private")

    def test_unproven_identity_cannot_be_assigned_to_other_player(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            write(ol, [scorer(), scorer("56", "Jugador Otro")])
            write(registry, [mapping(), mapping("56")])
            with self.assertRaisesRegex(ValueError, "colisión"):
                integrate(fifa, ol, registry, root / "private")

    def test_evidence_url_must_be_https(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            write(registry, [dict(mapping(), evidence_url="")])
            with self.assertRaisesRegex(ValueError, "evidencia externa"):
                integrate(fifa, ol, registry, root / "private")

    def test_unknown_player_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as dir:
            root, fifa, ol, registry = self.prepare(dir)
            write(registry, [mapping(fc_id="999")])
            with self.assertRaisesRegex(ValueError, "no existe"):
                integrate(fifa, ol, registry, root / "private")


if __name__ == "__main__":
    unittest.main()
