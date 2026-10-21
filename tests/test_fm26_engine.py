"""
Unit and Integration Test Suite for FM26 Stat & Rating Modifier.

Verifies:
- 1-20 display <-> 5-100 internal binary attribute scaling
- ACTUAL_PLAYER@db C++ struct and serialized DB offset mappings
- Inverse trait handling (Injury Proneness, Dirtiness, Eccentricity) during presets
- Accent-insensitive Name-Only player search across multi-word, common, and legal names
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fm_core import PlayerMemoryTarget, apply_preset_to_player
from fm_database import FMDatabase, normalize_name
from fm_schema import (
    ATTRIBUTE_DEFS,
    CPP_ATTR_OFFSET,
    CPP_CA_OFFSET,
    CPP_PA_OFFSET,
    CPP_POS_OFFSET,
    SER_ATTR_OFFSET,
    SER_CA_OFFSET,
    SER_PA_OFFSET,
    SER_POS_OFFSET,
    to_display_attr,
    to_raw_attr,
)


class TestFM26SchemaAndEngine(unittest.TestCase):
    def test_attribute_scale_roundtrip(self) -> None:
        for display_val in range(1, 21):
            raw = to_raw_attr(display_val)
            self.assertEqual(raw, display_val * 5)
            self.assertEqual(to_display_attr(raw), display_val)

    def test_cpp_and_serialized_struct_offsets(self) -> None:
        base = 0x7FF600001000
        cpp_t = PlayerMemoryTarget.from_cpp_object(735107, base)
        self.assertEqual(cpp_t.pos_address, base + CPP_POS_OFFSET)
        self.assertEqual(cpp_t.attr_address, base + CPP_ATTR_OFFSET)
        self.assertEqual(cpp_t.ca_address, base + CPP_CA_OFFSET)
        self.assertEqual(cpp_t.pa_address, base + CPP_PA_OFFSET)
        self.assertEqual(cpp_t.attr_address - cpp_t.pos_address, 15)

        ser_t = PlayerMemoryTarget.from_serialized_record(735107, base)
        self.assertEqual(ser_t.pos_address, base + SER_POS_OFFSET)
        self.assertEqual(ser_t.attr_address, base + SER_ATTR_OFFSET)
        self.assertEqual(ser_t.ca_address, base + SER_CA_OFFSET)
        self.assertEqual(ser_t.pa_address, base + SER_PA_OFFSET)
        self.assertEqual(ser_t.attr_address - ser_t.pos_address, 15)

    def test_name_only_search_queries(self) -> None:
        db = FMDatabase()
        expected = [
            ("Cristiano Ronaldo", 735107),
            ("Ronaldo", 735107),
            ("Bruno Fernandes", 43124199),
            ("Bernardo Silva", 55041623),
            ("Vitinha", 83174759),
            ("Diogo Costa", 83169004),
            ("Mbappe", 85138732),
            ("Odegaard", 53094112),
            ("Ruben Dias", 55070298),
            ("Vinicius", 19301965),
            ("Yamal", 2000256212),
            ("Haaland", 29179240),
        ]
        for query, expected_uid in expected:
            matches = db.search_players(query, limit=5)
            self.assertTrue(len(matches) > 0, f"No match found for query '{query}'")
            self.assertEqual(
                matches[0].uid,
                expected_uid,
                f"Expected top match UID {expected_uid} for '{query}', got {matches[0].uid} ({matches[0].display_name})",
            )

    def test_super_boost_respects_inverse_attributes(self) -> None:
        db = FMDatabase()
        cr7 = db.search_players("Cristiano Ronaldo", limit=1)[0]
        apply_preset_to_player(cr7, "super_boost")

        self.assertEqual(cr7.ca, 200)
        self.assertEqual(cr7.pa, 200)
        disp = cr7.get_display_attributes()
        # Positive outfield attributes must be 20 (100 raw)
        self.assertEqual(disp[2], 20)   # Finishing
        self.assertEqual(disp[7], 20)   # Passing
        self.assertEqual(disp[38], 20)  # Pace
        self.assertEqual(cr7.raw_attributes[2], 100)
        # Inverse attributes must be 1 (5 raw)
        self.assertEqual(disp[48], 1)   # Injury Proneness
        self.assertEqual(disp[41], 1)   # Dirtiness
        self.assertEqual(cr7.raw_attributes[48], 5)
        self.assertEqual(cr7.raw_attributes[41], 5)

    def test_normalize_name_strips_accents(self) -> None:
        self.assertEqual(normalize_name("Kylian Mbappé"), "kylian mbappe")
        self.assertEqual(normalize_name("Martin Ødegaard"), "martin odegaard")
        self.assertEqual(normalize_name("Vítor Machado Ferreira"), "vitor machado ferreira")

    def test_scout_exporter_and_comparison(self) -> None:
        from fm_scout import export_player_json, export_roster_csv, compare_players
        import tempfile

        p1 = {
            "uid": 735107,
            "name": "Cristiano Ronaldo",
            "nation": "Portugal",
            "club": "Al-Nassr",
            "age": 41,
            "ca": 165,
            "pa": 195,
            "attributes": {"Finishing": 19, "Pace": 15, "Determination": 20, "Composure": 18}
        }
        p2 = {
            "uid": 88031341,
            "name": "Kylian Mbappe",
            "nation": "France",
            "club": "Real Madrid",
            "age": 27,
            "ca": 188,
            "pa": 197,
            "attributes": {"Finishing": 18, "Pace": 20, "Determination": 16, "Composure": 17}
        }

        with tempfile.TemporaryDirectory() as td:
            # 1. JSON Export
            json_file = Path(td) / "cr7.json"
            export_player_json(p1, json_file)
            self.assertTrue(json_file.exists())
            self.assertIn("Cristiano Ronaldo", json_file.read_text(encoding="utf-8"))

            # 2. CSV Export
            csv_file = Path(td) / "scout_roster.csv"
            export_roster_csv([p1, p2], csv_file)
            self.assertTrue(csv_file.exists())
            csv_lines = csv_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(csv_lines), 3)

        # 3. Comparison
        cmp = compare_players(p1, p2)
        self.assertEqual(cmp["total_attributes_compared"], 4)
        self.assertEqual(cmp["attribute_matrix"]["Pace"]["advantage"], "Kylian Mbappe")
        self.assertEqual(cmp["attribute_matrix"]["Finishing"]["advantage"], "Cristiano Ronaldo")
        self.assertEqual(cmp["player_a_wins"], 3)
        self.assertEqual(cmp["player_b_wins"], 1)
        self.assertEqual(cmp["overall_winner"], "Cristiano Ronaldo")


if __name__ == "__main__":
    unittest.main()
