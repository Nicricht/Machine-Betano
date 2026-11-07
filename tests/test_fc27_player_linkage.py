"""Pruebas del cruce FC27/OpenLigaDB sin internet, con nombres ficticios."""
import tempfile
from pathlib import Path
import csv
import json
import unittest

from scripts.link_fc27_openligadb import (
    normalize_name, scorer_style, team_for_goal_events, propose_links, run,
)


def fc(pid="12", name="Nicolás Pérez", club="Club Atlético A"):
    return dict(
        fc_player_id=pid, name=name, club=club,
        edition="FC27", as_of_date="2026-09-12",
        position="ST", ovr="84",
    )


def match(mid="1", home="Club Atlético A", away="Club Deportivo B", hg="2", ag="1"):
    return dict(
        match_id=mid, league="la1", season_start_year="2026",
        home_team=home, away_team=away, home_goals=hg, away_goals=ag,
    )


def goal(mid="1", pid="99", name="N. Pérez", hg="1", ag="0", own=False):
    return dict(
        match_id=mid, league="la1", season_start_year="2026",
        player_id=pid, player_name=name,
        home_score_after_goal=hg, away_score_after_goal=ag,
        is_own_goal=str(own),
    )


class TestPlayerIdentityLinkage(unittest.TestCase):
    def test_accents_and_initials(self):
        self.assertEqual(normalize_name("Nicolás Pérez"), "nicolas perez")
        self.assertEqual(scorer_style("N. Pérez", "Nicolás Pérez"), "INITIAL_SURNAME")
        self.assertEqual(scorer_style("Nicolás Pérez", "Nicolas Perez"), "FULL_NAME_EXACT")
        self.assertEqual(scorer_style("Pérez", "Nicolás Pérez"), "SURNAME_ONLY")
        self.assertIsNone(scorer_style("M. Pérez", "Nicolás Pérez"))

    def test_goal_side_by_score_progression(self):
        matches = [match()]
        # Gol de la visita, luego local, luego local: los datos pueden estar
        # desordenados por minuto, pero la puntuación reconstruye el orden.
        goals = [
            goal(pid="31", name="Jugador A", hg="2", ag="1"),
            goal(pid="21", name="Jugador B", hg="0", ag="1"),
            goal(pid="31", name="Jugador A", hg="1", ag="1"),
        ]
        inferred, report = team_for_goal_events(matches, goals)
        clubs = {r["openligadb_player_id"]: r["club"] for r in inferred}
        self.assertEqual(clubs["31"], "Club Atlético A")
        self.assertEqual(clubs["21"], "Club Deportivo B")
        self.assertEqual(report["goal_events_with_team_inferred"], 3)

    def test_own_goal_reverses_scorer_club(self):
        goals = [goal(pid="21", name="Jugador B", hg="1", ag="0", own=True)]
        inferred, _ = team_for_goal_events([match(hg="1", ag="0")], goals)
        self.assertEqual(inferred[0]["club"], "Club Deportivo B")

    def test_invalid_score_sequence_never_links(self):
        matches = [match()]
        goals = [goal(hg="2", ag="0"), goal(hg="2", ag="1")]
        inferred, report = team_for_goal_events(matches, goals)
        self.assertEqual(inferred, [])
        self.assertEqual(report["matches_with_incomplete_or_invalid_goal_sequence"], 1)

    def test_exact_name_and_club_provisional_not_verified(self):
        players = [fc(name="Nicolás Pérez")]
        proposals, report = propose_links(players, [match(hg="1", ag="0")],
            [goal(name="Nicolás Pérez")])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["review_status"], "PROVISIONAL_EXACT")
        self.assertEqual(report["auto_approved_for_training"], 0)

    def test_initial_and_surname_requires_review(self):
        proposals, report = propose_links([fc()], [match(hg="1", ag="0")], [goal()])
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["review_status"], "REVIEW_INITIAL_SURNAME")
        self.assertEqual(report["proposed_mappings"], 1)

    def test_wrong_club_never_matches_same_name(self):
        proposals, report = propose_links([fc(club="Club C")],
                [match(hg="1", ag="0")], [goal(name="Nicolás Pérez")])
        self.assertEqual(proposals, [])
        self.assertEqual(report["scorer_ids_without_exact_club"], 1)

    def test_ambiguous_names_block_auto_provisional(self):
        players = [fc(pid="11"), fc(pid="12")]
        proposals, report = propose_links(players, [match(hg="1", ag="0")],
                                           [goal(name="Nicolás Pérez")])
        self.assertEqual(len(proposals), 2)
        self.assertTrue(all(x["review_status"] == "REVIEW_AMBIGUOUS" for x in proposals))
        self.assertEqual(report["scorer_ids_ambiguous"], 1)

    def test_ea_player_linked_to_two_scorer_ids_requires_review(self):
        players = [fc()]
        matches = [match(mid="1", hg="1", ag="0"), match(mid="2", hg="1", ag="0")]
        goals = [goal(mid="1", pid="111", name="Nicolás Pérez"),
                 goal(mid="2", pid="222", name="Nicolás Pérez")]
        proposals, report = propose_links(players, matches, goals)
        self.assertEqual(len(proposals), 2)
        self.assertEqual(report["ea_ids_linked_to_multiple_scorers"], 1)
        self.assertTrue(all(x["review_status"] == "REVIEW_EA_ID_COLLISION" for x in proposals))

    def test_full_pipeline_writes_private_candidates_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ratings = root / "ratings.csv"
            live = root / "live"
            private = root / "private"
            live.mkdir()
            def write(path, records):
                with path.open("w", encoding="utf-8", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=list(records[0]))
                    writer.writeheader()
                    writer.writerows(records)
            write(ratings, [fc(name="Nicolás Pérez")])
            write(live / "la1_2026_partidos.csv", [match(hg="1", ag="0")])
            write(live / "la1_2026_goleadores.csv", [goal(name="Nicolás Pérez")])
            (live / "ultima_actualizacion.json").write_text(json.dumps({
                "checked_at_utc": "2026-11-07T19:00:00Z",
                "leagues": [{"league": "la1", "season": 2026, "matches": 1}],
            }), encoding="utf-8")
            audit = run(ratings, live, private)
            self.assertEqual(audit["proposed_mappings"], 1)
            self.assertFalse(audit["ready_for_prediction"])
            self.assertFalse(audit["license_cleared"])
            self.assertTrue((private / "fc27_openligadb_candidates.csv").exists())
            self.assertTrue((private / "fc27_openligadb_linkage_audit.json").exists())


if __name__ == "__main__":
    unittest.main()
