"""Tests for the advanced research-contract / PIT tutorial (synthetic fixtures)."""
from __future__ import annotations

import copy
import unittest

from examples.advanced_protocol_pit_lab import (
    audit_snapshot, facts_asof, membership_asof, moment,
    sample_contract, sample_financial, sample_memberships, validate_contract,
)


class ResearchContractLabTests(unittest.TestCase):
    def test_sample_has_exact_asof_view_without_future_revision(self):
        result = audit_snapshot(
            sample_contract(), sample_memberships(), sample_financial(), "roe"
        )
        self.assertEqual([r["code"] for r in result["universe"]], ["A", "B"])
        self.assertEqual(result["facts"]["A"]["value"], 0.10)
        self.assertEqual(result["facts"]["B"]["period_end"], "2023-09-30")
        self.assertEqual(result["coverage"], {
            "eligible": 2, "known_values": 2, "missing_values": 0,
        })

    def test_revised_fact_visible_only_after_its_known_at(self):
        facts = sample_financial()
        before = facts_asof(facts, "2024-04-09T18:00:00+08:00", "2024-04-09", "roe", ["A"])
        after = facts_asof(facts, "2024-04-11T18:00:00+08:00", "2024-04-11", "roe", ["A"])
        self.assertEqual(before["A"]["value"], 0.10)
        self.assertEqual(after["A"]["value"], 0.15)

    def test_missing_facts_remain_missing(self):
        facts = facts_asof(
            sample_financial(), "2024-03-20T15:00:00+08:00",
            "2024-03-20", "roe", ["A", "D"]
        )
        self.assertIsNone(facts["D"])

    def test_half_open_end_excludes_stock_on_end_day(self):
        members = sample_memberships()
        before = membership_asof(members, "2024-03-21T15:00:00+08:00", "2024-03-20")
        at_end = membership_asof(members, "2024-03-21T15:00:00+08:00", "2024-03-21")
        self.assertIn("B", [r["code"] for r in before])
        self.assertNotIn("B", [r["code"] for r in at_end])

    def test_late_membership_not_retroactively_known(self):
        members = sample_memberships()
        early = membership_asof(members, "2024-03-20T15:00:00+08:00", "2024-03-20")
        self.assertNotIn("C", [r["code"] for r in early])

    def test_naive_timestamp_rejected_even_if_order_looks_valid(self):
        contract = sample_contract()
        contract["feature_available_at"] = "2024-03-20T15:00:00"
        with self.assertRaisesRegex(ValueError, "offset"):
            validate_contract(contract)

    def test_absolute_instants_not_lexical_clock_strings(self):
        self.assertLess(moment("2024-03-20T01:00:00-07:00"),
                        moment("2024-03-20T18:00:00+08:00"))

    def test_overlap_requires_purge(self):
        contract = sample_contract()
        contract["train_last_label_end_at"] = contract["valid_first_signal_at"]
        with self.assertRaisesRegex(ValueError, "purge"):
            validate_contract(contract)

    def test_feature_cannot_arrive_after_decision(self):
        contract = sample_contract()
        contract["feature_available_at"] = "2024-03-20T19:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "cutoff"):
            validate_contract(contract)

    def test_duplicate_announcement_is_rejected(self):
        facts = sample_financial()
        facts.append(copy.deepcopy(facts[0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            facts_asof(facts, "2024-03-20T15:00:00+08:00", "2024-03-20", "roe", ["A"])

    def test_nonfinite_value_rejected(self):
        facts = sample_financial()
        facts[0]["value"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            facts_asof(facts, "2024-03-20T15:00:00+08:00", "2024-03-20", "roe", ["A"])


if __name__ == "__main__":
    unittest.main()
