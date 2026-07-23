#!/usr/bin/env python3
"""Public repository contract test.

Asserts that the local copy of ``liga_pro/canonical_v2_contract.py``
matches the canonical constants required by the coordinated delivery.
"""
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "liga_pro"))

import canonical_v2_contract as contract  # noqa: E402


EXPECTED_FIXTURE_ROW_SHA256 = (
    "193a8fe943409a7a111257259efc8d1bc1aed91df1d5b8770903a34dd04dc654"
)
EXPECTED_FIXTURE_SNAPSHOT_SHA256 = (
    "52b00de02b8e09c4c20feaaad5a6f4d9a700100c12136ed42c45ea0e9ebfe39d"
)


class CanonicalContractTests(unittest.TestCase):

    def test_method_enum(self):
        self.assertEqual(
            tuple(contract.METHODS),
            ("OFFICIAL", "SCHEDULED_START_PLUS_DURATION", "UNAVAILABLE"),
        )

    def test_match_fields_order_length(self):
        self.assertEqual(len(contract.MATCH_FIELDS), 27)
        # First and last must be the canonical identity columns.
        self.assertEqual(contract.MATCH_FIELDS[0], "match_id")
        self.assertEqual(contract.MATCH_FIELDS[-1], "content_hash")

    def test_hash_exclude(self):
        self.assertEqual(
            set(contract.HASH_EXCLUDE),
            {"content_hash", "last_changed_at_utc", "source_snapshot_id"},
        )

    def test_fixture_row_sha(self):
        self.assertEqual(
            contract.FIXTURE_ROW_SHA256, EXPECTED_FIXTURE_ROW_SHA256
        )

    def test_fixture_snapshot_sha(self):
        self.assertEqual(
            contract.FIXTURE_SNAPSHOT_SHA256, EXPECTED_FIXTURE_SNAPSHOT_SHA256
        )

    def test_contract_file_byte_identical_to_canonical(self):
        """The local copy must byte-equal the upstream canonical source."""
        canonical = Path("/root/TT/scripts/canonical_v2_contract.py")
        if not canonical.exists():
            self.skipTest("canonical source not present")
        local = ROOT / "liga_pro" / "canonical_v2_contract.py"
        a = hashlib.sha256(canonical.read_bytes()).hexdigest()
        b = hashlib.sha256(local.read_bytes()).hexdigest()
        self.assertEqual(a, b,
                         f"contract file diverged from canonical: {a} vs {b}")


if __name__ == "__main__":
    unittest.main()
