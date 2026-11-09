"""Auditoría de metadata Hugging Face con fixtures sintéticos, sin descargas."""
import unittest

from scripts.audit_hf_soccer_metadata import (
    analyze_catalogue, build_report, inspect_schema, pick_target,
)

REVISION = "a" * 40


def league(name="La Liga", country="Spain", in_dataset=True, **other):
    return {
        "af_name": name, "af_country": country,
        "in_dataset": in_dataset, "history_status": "recent_only",
        "af_league_id": 140, "min_season": 2010,
        "max_season": 2026, "present_years": 5,
        "af_has_stats": True, **other,
    }


def package():
    return {
        "resources": [
            {"name": "fixtures", "rows": 670000,
             "schema": {"fields": [{"name": x} for x in ("id", "league_id", "date_utc")]}},
            {"name": "fixture_players_stats_flat", "rows": 4900000,
             "schema": {"fields": [{"name": x} for x in
                                    ("fixture_id", "player_id", "games_minutes", "shots_total")]}},
        ]
    }


class MetadataAuditorTests(unittest.TestCase):
    def test_identifies_only_first_division(self):
        self.assertEqual(pick_target(league()), "la1")
        self.assertEqual(pick_target(league(name="Bundesliga", country="Germany")), "bl1")
        self.assertIsNone(pick_target(league(name="2. Bundesliga", country="Germany")))
        self.assertIsNone(pick_target(league(name="La Liga", country="Colombia")))

    def test_catalogue_presence_is_not_observed_player_coverage(self):
        report = analyze_catalogue([
            league(),
            league(name="Bundesliga", country="Germany"),
            league(name="2. Bundesliga", country="Germany"),
        ])
        self.assertEqual(report["catalogue_rows"], 3)
        self.assertEqual(len(report["selected_leagues"]["bl1"]), 1)
        self.assertEqual(report["selection_status"]["la1"], "FOUND_CATALOGUE_ONLY")
        self.assertTrue(report["cannot_infer_from_catalogue"])

    def test_missing_league_not_assumed_zero_stats(self):
        report = analyze_catalogue([league(name="Serie A", country="Italy")])
        self.assertEqual(report["selected_leagues"]["la1"], [])
        self.assertEqual(report["selection_status"]["bl1"], "NOT_FOUND_IN_CATALOGUE")

    def test_schema_column_checks(self):
        rows = inspect_schema(package())
        self.assertEqual(rows["fixtures"]["essential_columns_missing"], [])
        self.assertEqual(rows["fixture_players_stats_flat"]["declared_rows"], 4900000)
        self.assertFalse(rows["fixture_players"]["present_in_metadata"])

    def test_report_never_claims_rights_or_training_clearance(self):
        report = build_report([league()], package(), REVISION,
                              ["README.md", "datapackage.json"], "2026-11-08T00:00:00Z")
        self.assertFalse(report["approved_for_model_training"])
        self.assertFalse(report["approved_for_master_dataset"])
        self.assertFalse(report["upstream_use_rights_verified"])
        self.assertFalse(report["large_data_files_downloaded"])
        self.assertEqual(report["scope"], "METADATA_ONLY")
        self.assertNotIn("sample_rows", report)

    def test_invalid_revision_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA40"):
            build_report([league()], package(), "main", ["README.md"])

    def test_empty_catalogue_rejected(self):
        with self.assertRaisesRegex(ValueError, "vacío"):
            analyze_catalogue([])


if __name__ == "__main__":
    unittest.main()
