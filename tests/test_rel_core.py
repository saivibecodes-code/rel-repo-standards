"""
Unit tests for rel_core utilities in rel-repo-standards.
"""

import unittest

from rel_core.addresses import (
    clean_address,
    normalize_street_address,
    parse_street_address,
)
from rel_core.motivation import (
    calculate_motivation_score,
    get_priority_tier,
)
from rel_core.universal_id import (
    generate_universal_id,
    parse_universal_id,
    resolve_fips,
)


class TestRelCore(unittest.TestCase):
    def test_resolve_fips(self):
        self.assertEqual(resolve_fips("Collin"), "48085")
        self.assertEqual(resolve_fips("DENTON"), "48121")
        self.assertEqual(resolve_fips("48113"), "48113")
        with self.assertRaises(ValueError):
            resolve_fips("UNKNOWN_COUNTY")

    def test_generate_and_parse_universal_id(self):
        uid_collin = generate_universal_id("Collin", 821)
        self.assertEqual(uid_collin, "48085_821")

        uid_denton = generate_universal_id("48121", "100")
        self.assertEqual(uid_denton, "48121_100")

        fips, prop_id = parse_universal_id("48085_821")
        self.assertEqual(fips, "48085")
        self.assertEqual(prop_id, "821")

    def test_clean_and_normalize_address(self):
        raw = "1234 North Main Street, Apt 4B."
        cleaned = clean_address(raw)
        self.assertNotIn(".", cleaned)
        self.assertNotIn(",", cleaned)

        normalized = normalize_street_address(raw)
        self.assertEqual(normalized, "1234 N MAIN ST APT 4B")

        norm_court = normalize_street_address("555 Elm Court")
        self.assertEqual(norm_court, "555 ELM CT")

    def test_parse_street_address(self):
        num, pre_dir, street, suffix = parse_street_address("789 W ELM ST")
        self.assertEqual(num, "789")
        self.assertEqual(pre_dir, "W")
        self.assertEqual(street, "ELM")
        self.assertEqual(suffix, "ST")

        num2, pre_dir2, street2, suffix2 = parse_street_address("100 MAIN")
        self.assertEqual(num2, "100")
        self.assertIsNone(pre_dir2)
        self.assertEqual(street2, "MAIN")
        self.assertIsNone(suffix2)

    def test_motivation_score_and_priority(self):
        flags_urgent = {
            "has_pre_foreclosure": 1,
            "has_auction_scheduled": 1,
            "has_delinquent_tax": 1,
        }
        score = calculate_motivation_score(flags_urgent)
        self.assertGreaterEqual(score, 80)
        self.assertEqual(get_priority_tier(score, has_auction=True), "URGENT")

        flags_watch = {"is_absentee": 1}
        score_watch = calculate_motivation_score(flags_watch)
        self.assertEqual(score_watch, 10)
        self.assertEqual(get_priority_tier(score_watch, has_auction=False), "WATCHLIST")


if __name__ == "__main__":
    unittest.main()
