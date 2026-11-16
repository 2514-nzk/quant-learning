"""Boundary tests for the Chapter 10 synthetic execution replay."""
from __future__ import annotations
import copy
import unittest

from examples.volume3_execution_replay_lab import (
    evaluate, load_fixture, replay_ioc, replay_passive, validate
)


class Volume3ExecutionReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_fixture()
        cls.result = evaluate(cls.data)
        cls.rows = cls.result["execution_outcomes"]

    def row(self, order_id, latency, cancel_credit=None):
        return next(x for x in self.rows if x["order_id"] == order_id
                    and x["latency_ms"] == latency
                    and x.get("cancel_credit_identified_ahead") == cancel_credit)

    def order(self, order_id):
        return next(x for x in self.data["orders"] if x["order_id"] == order_id)

    def test_fixture_is_synthetic_and_makes_no_live_execution_claim(self):
        self.assertEqual(self.data["evidence_grade"], "SYNTHETIC_ONLY")
        source = self.data["source_contract"]
        self.assertFalse(source["is_exchange_raw"])
        self.assertFalse(source["is_qmt_tick"])
        self.assertFalse(source["is_real_market_data"])
        self.assertFalse(self.result["claims"]["real_market_execution_proven"])
        self.assertFalse(self.result["claims"]["real_fill_probability_calibrated"])
        self.assertFalse(self.result["claims"]["strategy_alpha_proven"])

    def test_latency_and_queue_position_make_touch_only_assumption_optimistic(self):
        expected = {50: (500, 200), 150: (200, 0), 350: (200, 200)}
        for latency, (with_cancel_credit, no_cancel_credit) in expected.items():
            credited = self.row("P_MAIN", latency, True)
            conservative = self.row("P_MAIN", latency, False)
            self.assertEqual(credited["filled_qty"], with_cancel_credit)
            self.assertEqual(conservative["filled_qty"], no_cancel_credit)
            self.assertEqual(credited["touch_only_assumed_qty"], 500)
            self.assertEqual(conservative["touch_only_assumed_qty"], 500)
        self.assertEqual(self.row("P_MAIN", 150, True)["initial_queue_ahead_qty"], 1300)
        self.assertEqual(self.row("P_MAIN", 350, True)["initial_queue_ahead_qty"], 300)

    def test_trade_volume_consumes_fifo_queue_before_our_order(self):
        row = self.row("P_MAIN", 50, True)
        self.assertEqual(row["initial_queue_ahead_qty"], 1000)
        self.assertEqual(row["trade_volume_at_limit_qty"], 1200)
        self.assertEqual(row["fills"], [
            {"exchange_time":"2099-01-02T09:30:00.500+08:00","price_ticks":10000,"quantity":300},
            {"exchange_time":"2099-01-02T09:30:00.650+08:00","price_ticks":10000,"quantity":200}
        ])
        self.assertEqual(row["filled_qty"], 500)
        self.assertEqual(row["queue_ahead_remaining_qty"], 0)

    def test_only_identified_ahead_cancellations_reduce_queue(self):
        credit = self.row("P_MAIN", 50, True)
        conservative = self.row("P_MAIN", 50, False)
        self.assertEqual(credit["cancel_credit_qty"], 300)
        self.assertEqual(conservative["cancel_credit_qty"], 0)
        self.assertEqual(credit["filled_qty"], 500)
        self.assertEqual(conservative["filled_qty"], 200)

    def test_ioc_walks_opposite_depth_without_exceeding_limit(self):
        row = self.row("IOC_OK", 50, None)
        self.assertEqual(row["status"], "FILLED")
        self.assertEqual(row["filled_qty"], 400)
        self.assertEqual([(x["price_ticks"],x["quantity"]) for x in row["fills"]],
                         [(10003,200),(10004,200)])
        self.assertEqual(row["vwap_ticks"], 10003.5)
        changed = copy.deepcopy(self.data)
        order = next(x for x in changed["orders"] if x["order_id"] == "IOC_OK")
        order["limit_price_ticks"] = 10003
        validate(changed)
        limited = replay_ioc(order,50,changed)
        self.assertEqual(limited["filled_qty"], 200)
        self.assertEqual(limited["unfilled_qty"], 200)
        self.assertEqual(limited["status"], "PARTIALLY_FILLED_IOC_CANCELLED")
        self.assertTrue(all(x["price_ticks"] <= 10003 for x in limited["fills"]))

    def test_stale_book_is_rejected_instead_of_filling_from_old_quote(self):
        row = self.row("IOC_STALE",250,None)
        self.assertEqual(row["status"], "STALE_BOOK_REJECTED")
        self.assertEqual(row["quote_age_ms"], 210.0)
        self.assertEqual(row["filled_qty"], 0)
        self.assertIsNone(row["vwap_ticks"])

    def test_cancel_replace_is_a_new_order_with_a_new_queue_position(self):
        old = self.row("R_OLD",50,True)
        new = self.row("R_NEW",50,True)
        self.assertEqual(old["filled_qty"], 0)
        self.assertEqual(new["initial_queue_ahead_qty"], 200)
        self.assertEqual(new["filled_qty"], 500)
        self.assertEqual(self.result["cancel_replace"]["replacement_parent_id"], "R_OLD")
        self.assertLess(self.order("R_OLD")["expiry_time"], self.order("R_NEW")["submit_time"])

    def test_shortfall_fees_and_markout_are_separate(self):
        ioc = self.row("IOC_OK",50,None)
        self.assertAlmostEqual(ioc["price_shortfall_bps"], 1.4997000599880024)
        self.assertAlmostEqual(ioc["fee_bps"], 2.0)
        self.assertAlmostEqual(ioc["total_cost_bps"], 3.4997000599880024)
        self.assertAlmostEqual(ioc["markout_bps"], -2.4991003298770464)
        passive = self.row("P_MAIN",50,True)
        self.assertAlmostEqual(passive["markout_bps"], 1.0)

    def test_no_fill_has_no_fabricated_vwap_or_cost(self):
        row = self.row("P_MAIN",150,False)
        self.assertEqual(row["filled_qty"], 0)
        self.assertIsNone(row["vwap_ticks"])
        self.assertIsNone(row["price_shortfall_bps"])
        self.assertIsNone(row["fee_bps"])
        self.assertIsNone(row["markout_bps"])

    def test_trade_after_expiry_cannot_fill_cancelled_order(self):
        row = self.row("R_OLD",50,True)
        self.assertEqual(row["touch_only_assumed_qty"], 0)
        self.assertEqual(row["filled_qty"], 0)

    def test_future_only_snapshot_is_not_available_at_order_arrival(self):
        order = copy.deepcopy(self.order("IOC_OK"))
        order["book_snapshots"][0]["available_at"] = "2099-01-02T09:30:00.300+08:00"
        validate({**self.data,"orders":[order] + [x for x in self.data["orders"] if x["order_id"] != "IOC_OK"]})
        row = replay_ioc(order,50,{**self.data,"orders":[order]})
        self.assertEqual(row["status"], "NO_VALID_BOOK")
        self.assertEqual(row["filled_qty"], 0)

    def test_invalid_order_clock_and_unknown_queue_cancel_are_rejected(self):
        bad = copy.deepcopy(self.data)
        bad["orders"][0]["decision_time"] = "2099-01-02T09:30:00.090+08:00"
        with self.assertRaisesRegex(ValueError,"chronology"):
            validate(bad)
        bad = copy.deepcopy(self.data)
        bad["orders"][0]["events"][1]["order_id"] = "NOT_AHEAD"
        with self.assertRaisesRegex(ValueError,"does not identify an ahead order"):
            validate(bad)

    def test_cancel_cannot_exceed_remaining_ahead_quantity(self):
        order = copy.deepcopy(self.order("P_MAIN"))
        order["events"][1]["cancelled_qty"] = 500
        with self.assertRaisesRegex(ValueError,"exceeds remaining queue"):
            replay_passive(order,50,True,self.data)


if __name__ == "__main__":
    unittest.main()
