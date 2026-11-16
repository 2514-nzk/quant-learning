"""Deterministic boundary tests for the Chapter 09 synthetic L2 audit lab."""
from __future__ import annotations
import copy
import unittest

from examples.volume3_l2_auction_lab import (
    classify_measurement, evaluate, load_fixture, validate
)

class Volume3L2AuctionLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_fixture()
        cls.result = evaluate(cls.data)

    def test_fixture_is_synthetic_and_not_qmt_or_exchange_raw(self):
        self.assertEqual(self.data["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertFalse(self.data["source_contract"]["is_exchange_raw"])
        self.assertFalse(self.data["source_contract"]["is_qmt_tick"])
        self.assertFalse(self.result["claims"]["real_market_L2_validated"])
        self.assertFalse(self.result["claims"]["qmt_tick_equivalence_proven"])
        self.assertFalse(self.result["claims"]["strategy_alpha_proven"])

    def test_auction_cutoff_is_inclusive_at_0920(self):
        rows = self.result["auction"]["snapshots"]
        self.assertEqual([x["imbalance_ratio"]["value"] for x in rows],
                         [0.5, 0.25, 0.75])
        self.assertEqual(
            [x["indicative_price_ticks"] for x in rows], [10002, 10004, 10005]
        )
        self.assertEqual(self.result["auction"]["final_opening_price_ticks"], 10006)
        self.assertEqual(
            self.result["auction"]["last_indicative_minus_final_price_ticks"], -1
        )
        bad = copy.deepcopy(self.data)
        bad["session"]["auction_snapshots"][1]["rule_derived_cancel_allowed"] = True
        with self.assertRaisesRegex(ValueError, "09:20 cutoff"):
            validate(bad)

    def test_order_lifecycle_reconciles_by_side_and_size_bucket(self):
        ledger = self.result["order_lifecycle"]
        self.assertEqual((ledger["order_count"], ledger["trade_count"],
                          ledger["unique_trade_qty"]), (11, 4, 1000))
        buy, sell = ledger["by_side"]["BUY"], ledger["by_side"]["SELL"]
        self.assertEqual(
            (buy["submitted_qty"], buy["cancelled_qty"], buy["executed_qty"],
             buy["open_qty"]), (2450, 450, 1000, 1000)
        )
        self.assertEqual(
            (sell["submitted_qty"], sell["cancelled_qty"], sell["executed_qty"],
             sell["open_qty"]), (2300, 1000, 1000, 300)
        )
        self.assertTrue(buy["lifecycle_reconciles"])
        self.assertTrue(sell["lifecycle_reconciles"])
        self.assertEqual(ledger["by_size_bucket"]["BUY_LARGE"]["submitted_qty"], 1900)
        self.assertEqual(ledger["by_size_bucket"]["SELL_SMALL"]["executed_qty"], 600)

    def test_cancel_cannot_exceed_remaining_order_quantity(self):
        bad = copy.deepcopy(self.data)
        bad["session"]["order_trade_events"][4]["cancelled_qty"] = 501
        with self.assertRaisesRegex(ValueError, "exceeds remaining"):
            validate(bad)

    def test_trade_must_link_to_existing_opposite_side_orders(self):
        bad = copy.deepcopy(self.data)
        bad["session"]["order_trade_events"][6]["buy_order_id"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "unknown order"):
            validate(bad)
        bad = copy.deepcopy(self.data)
        bad["session"]["order_trade_events"][6]["quantity"] = 1001
        with self.assertRaisesRegex(ValueError, "exceeds remaining"):
            validate(bad)

    def test_book_features_have_defined_ofi_and_depth_imbalance(self):
        rows = self.result["book_features"]
        self.assertEqual([x["ofi_shares"] for x in rows],
                         [None, 0, 100, 150, 300, -150])
        self.assertEqual(rows[0]["ofi_status"], "NOT_APPLICABLE_FIRST_SNAPSHOT")
        self.assertAlmostEqual(rows[-1]["top1_imbalance"]["value"], 1/7)
        self.assertAlmostEqual(rows[-1]["top5_imbalance"]["value"], 0.2)
        self.assertEqual(rows[-1]["spread_ticks"], 3)

    def test_crossed_book_and_out_of_order_receive_time_are_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["session"]["book_snapshots"][0]["asks"][0]["price_ticks"] = 10009
        with self.assertRaisesRegex(ValueError, "cannot be crossed"):
            validate(bad)
        bad = copy.deepcopy(self.data)
        bad["session"]["order_trade_events"][0]["receive_time"] = (
            bad["session"]["order_trade_events"][0]["exchange_time"]
        )
        # Equal exchange/receive timestamps are valid; make receive time earlier instead.
        bad["session"]["order_trade_events"][0]["receive_time"] = "2099-01-01T09:30:00.000+08:00"
        with self.assertRaisesRegex(ValueError, "receive-time"):
            validate(bad)

    def test_zero_missing_undefined_and_not_applicable_are_distinct(self):
        rows = {x["case_id"]: x for x in self.result["measurement_semantics"]}
        self.assertEqual(rows["Q_ZERO"]["status"], "OBSERVED_ZERO")
        self.assertEqual(rows["Q_ZERO"]["value"], 0)
        self.assertEqual(rows["Q_COVERAGE"]["status"], "MISSING_SOURCE_COVERAGE")
        self.assertEqual(rows["Q_DENOM"]["status"], "UNDEFINED_ZERO_DENOMINATOR")
        self.assertEqual(rows["Q_NA"]["status"], "NOT_APPLICABLE")
        self.assertEqual(rows["Q_FIELD"]["status"], "MISSING_FIELD")
        self.assertIsNone(rows["Q_FIELD"]["value"])

    def test_measurement_ratio_does_not_turn_zero_denominator_into_zero(self):
        self.assertEqual(
            classify_measurement(0, 0, True, True),
            {"value": None, "status": "UNDEFINED_ZERO_DENOMINATOR"}
        )
        self.assertEqual(
            classify_measurement(0, 100, True, True),
            {"value": 0.0, "status": "OBSERVED_ZERO"}
        )

if __name__ == "__main__":
    unittest.main()
