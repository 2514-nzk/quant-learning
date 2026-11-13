"""Tests of synthetic portfolio allocation, execution and immutable reports."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from examples.advanced_portfolio_execution_lab import (
    CONFIG, EXPECTED_CODES, apply_order, audit_simulation, current_weights,
    holdings_qty, mark_to_market, optimize_weights, run_lab, settled_qty,
    simulate, synthetic_market, trade_to_target, validate_market,
)


class PortfolioExecutionTests(unittest.TestCase):
    def test_full_report_deterministic_and_reconciled(self):
        report = run_lab()
        again = run_lab()
        self.assertEqual(report["report_sha256"], again["report_sha256"])
        self.assertEqual(report["input_days"], 14)
        self.assertEqual(set(report["cases"]), {"cash", "equal_weight", "optimized"})
        self.assertTrue(all(a["cash_reconciles"] and a["nav_reconciles"]
                            for a in report["audit"].values()))
        self.assertIn("SYNTHETIC_ONLY", report["source_kind"])
        self.assertEqual(report["cases"]["cash"]["final_nav"], CONFIG["initial_cash"])
        self.assertGreater(report["cases"]["optimized"]["fill_count"], 0)

    def test_target_weight_and_sector_caps(self):
        market = synthetic_market()
        first = optimize_weights(market[0], market[:1], {}, CONFIG)
        target = first["target"]
        self.assertLessEqual(sum(target.values()), 1.000001)
        self.assertLessEqual(max(target.values()), CONFIG["max_stock_weight"]+1e-8)
        for sector in {row["sector"] for row in market[0]}:
            subtotal = sum(target[row["code"]] for row in market[0]
                           if row["sector"] == sector)
            self.assertLessEqual(subtotal, CONFIG["max_sector_weight"]+1e-8)
        self.assertLessEqual(first["weight_l1_change"],
                             CONFIG["max_weight_l1_change"]+1e-8)
        self.assertGreater(first["candidates_checked"], 0)

    def test_risk_uses_no_future_close(self):
        market = synthetic_market()
        original = optimize_weights(market[4], market[:5], {}, CONFIG)
        altered = copy.deepcopy(market)
        altered[5][0]["close"] *= 1.9
        altered[5][0]["score"] += 500
        result = optimize_weights(altered[4], altered[:5], {}, CONFIG)
        self.assertEqual(original, result)
        self.assertEqual(original["risk_data"]["latest_used_date"], market[4][0]["date"])

    def test_t_plus_one_blocks_same_day_sale(self):
        market = synthetic_market()
        lots = {}
        cash, buy = apply_order("BUY", "S01", 100, market[0][0], 100000, lots, CONFIG)
        self.assertEqual(buy["filled_qty"], 100)
        self.assertEqual(settled_qty(lots, "S01", market[0][0]["date"]), 0)
        cash, sale = apply_order("SELL", "S01", 100, market[0][0], cash, lots, CONFIG)
        self.assertEqual(sale["filled_qty"], 0)
        self.assertEqual(sale["reason"], "T_PLUS_1")
        self.assertEqual(holdings_qty(lots, "S01"), 100)
        cash, sold_next_day = apply_order("SELL", "S01", 100, market[1][0], cash, lots, CONFIG)
        self.assertEqual(sold_next_day["filled_qty"], 100)
        self.assertEqual(holdings_qty(lots, "S01"), 0)

    def test_buy_locked_sell_locked_and_suspended_rejections(self):
        market = synthetic_market()
        lots = {"S02": [{"acquired_on": market[0][0]["date"], "qty": 100}]}
        locked_buy = next(r for r in market[3] if r["code"] == "S01")
        locked_sell = next(r for r in market[6] if r["code"] == "S02")
        suspended = next(r for r in market[9] if r["code"] == "S03")
        _, a = apply_order("BUY", "S01", 100, locked_buy, 100000, lots, CONFIG)
        _, b = apply_order("SELL", "S02", 100, locked_sell, 100000, lots, CONFIG)
        _, c = apply_order("BUY", "S03", 100, suspended, 100000, lots, CONFIG)
        self.assertEqual([a["reason"], b["reason"], c["reason"]],
                         ["BUY_LOCKED", "SELL_LOCKED", "SUSPENDED"])
        self.assertTrue(all(e["status"] == "REJECTED" for e in (a, b, c)))

    def test_purchase_respects_cash_and_lots(self):
        market = synthetic_market()
        lots = {}
        # Request many lots with insufficient funds. Lower-order fills if affordable.
        cash, event = apply_order("BUY", "S01", 10000, market[0][0], 2900, lots, CONFIG)
        self.assertGreater(event["filled_qty"], 0)
        self.assertLess(event["filled_qty"], 10000)
        self.assertEqual(event["filled_qty"] % CONFIG["lot_size"], 0)
        self.assertGreaterEqual(cash, 0)
        self.assertEqual(event["status"], "PARTIAL")

    def test_trade_costs_tax_only_sell_and_consistent_cash(self):
        market = synthetic_market()
        lots = {}
        cash, buy = apply_order("BUY", "S01", 100, market[0][0], 100000, lots, CONFIG)
        self.assertGreater(buy["execution_price"], buy["quote_open"])
        self.assertEqual(buy["tax"], 0)
        cash, sell = apply_order("SELL", "S01", 100, market[1][0], cash, lots, CONFIG)
        self.assertLess(sell["execution_price"], sell["quote_open"])
        self.assertGreater(sell["tax"], 0)
        self.assertAlmostEqual(cash, 100000-buy["notional"]-buy["commission"]
                               +sell["notional"]-sell["commission"]-sell["tax"])

    def test_volume_cap_is_partial_and_logged(self):
        market = synthetic_market()
        lots = {}
        cash, event = apply_order("BUY", "S01", 10000, market[0][0],
                                  1_000_000, lots, CONFIG)
        self.assertEqual(event["filled_qty"], 8000)
        self.assertEqual(event["reason"], "VOLUME_CAP")

    def test_mark_to_market_and_ledger_tampering_detected(self):
        market = synthetic_market()
        out = simulate(market, CONFIG, "optimized")
        self.assertTrue(audit_simulation(out, CONFIG)["nav_reconciles"])
        tampered = copy.deepcopy(out)
        tampered["snapshots"][-1]["nav"] += 1
        with self.assertRaisesRegex(ValueError, "NAV"):
            audit_simulation(tampered, CONFIG)
        tampered = copy.deepcopy(out)
        tampered["ledger"][0]["cash_after"] += 1
        with self.assertRaisesRegex(ValueError, "cash"):
            audit_simulation(tampered, CONFIG)

    def test_invalid_calendar_and_future_features_rejected(self):
        market = synthetic_market()
        copy_market = copy.deepcopy(market)
        copy_market[1][0]["date"] = copy_market[0][0]["date"]
        with self.assertRaisesRegex(ValueError, "mixed"):
            validate_market(copy_market)
        copy_market = copy.deepcopy(market)
        copy_market[0][0]["score_known_at"] = "2024-07-01T19:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "signal"):
            validate_market(copy_market)

    def test_order_validates_lots_and_unknown_policy(self):
        market = synthetic_market()
        with self.assertRaisesRegex(ValueError, "full lot"):
            apply_order("BUY", "S01", 101, market[0][0], 100000, {}, CONFIG)
        with self.assertRaisesRegex(ValueError, "unknown"):
            simulate(market, CONFIG, "long_short_unapproved")

    def test_report_has_no_unsourced_live_claim(self):
        report = run_lab()
        self.assertGreater(len(report["limitations"]), 4)
        self.assertTrue(all(x in report for x in
                            ("config_sha256", "input_sha256", "report_sha256", "code_sha256")))
        self.assertTrue(all(row["latest_feature_known_at"] <= row["decision_at"]
                            for row in report["cases"]["optimized"]["decisions"]))


if __name__ == "__main__":
    unittest.main()
