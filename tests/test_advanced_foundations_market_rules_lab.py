"""Synthetic math / time-series / official-rule-version teaching tests."""
from __future__ import annotations

import copy
import math
import unittest

from examples.advanced_foundations_market_rules_lab import (
    SOURCE_KIND, autocorrelation, circular_block_ci, conditional_mean,
    hac_mean_se, iid_mean_se, known_before_decision, log_return,
    next_session, ols_1d, price_band, ridge_1d, ridge_gradient_check,
    run_lab, sample_covariance, simple_return, synthetic_ar1,
    trading_rule, two_asset_grid, validate_buy_size,
)


class FoundationsAndMarketRulesTests(unittest.TestCase):
    def test_full_output_stable_and_explicitly_non_market(self):
        one, two = run_lab(), run_lab()
        self.assertEqual(one["report_sha256"], two["report_sha256"])
        self.assertTrue(one["source_kind"].startswith("SYNTHETIC_"))
        self.assertIn("2026-07-06", " ".join(one["limitations"]))
        self.assertEqual(len(one["market_rules"]["versioned_profiles"]), 7)

    def test_hand_calculated_sample_covariance_and_ols(self):
        x, y = [1.,2.,3.], [2.,4.,6.]
        self.assertAlmostEqual(sample_covariance(x, y), 2.0)
        fit = ols_1d(x, y)
        self.assertAlmostEqual(fit["slope"], 2.)
        self.assertAlmostEqual(fit["intercept"], 0.)

    def test_constant_factor_has_no_identifiable_slope(self):
        with self.assertRaises((ValueError, ZeroDivisionError)):
            ols_1d([2.,2.,2.], [1.,2.,3.])
        with self.assertRaisesRegex(ValueError, "constant"):
            ridge_1d([2.,2.,2.], [1.,2.,3.], 0.3)

    def test_ridge_shrinks_slope_and_gradient_matches(self):
        x=[0.,1.,2.,3.,4.]
        y=[1.,2.,3.,5.,5.]
        self.assertLess(abs(ridge_1d(x,y,.5)["slope"]),
                        abs(ols_1d(x,y)["slope"]))
        self.assertLess(ridge_gradient_check(x,y,.5), 1e-8)
        with self.assertRaises(ValueError):
            ridge_1d(x,y,-.1)

    def test_conditional_mean_empty_event_is_undefined(self):
        self.assertEqual(conditional_mean([1.,3.,5.], [False,True,True]), 4.)
        with self.assertRaisesRegex(ValueError, "undefined"):
            conditional_mean([1.,3.], [False,False])

    def test_grid_optimization_respects_cash_and_nonnegative(self):
        result=two_asset_grid([.02,.01],[[.001,.0002],[.0002,.0008]])
        self.assertGreaterEqual(result["cash"],-1e-10)
        self.assertTrue(all(w>=0 for w in result["weights"]))
        self.assertAlmostEqual(sum(result["weights"])+result["cash"],1.)

    def test_simple_and_log_return_compound_exactly(self):
        r1=simple_return(100.,110.)
        r2=simple_return(110.,99.)
        self.assertAlmostEqual((1+r1)*(1+r2)-1, -.01)
        self.assertAlmostEqual(math.exp(log_return(100.,110.)+
                                        log_return(110.,99.))-1, -.01)
        with self.assertRaises(ValueError):
            log_return(0.,2.)

    def test_autocorrelated_series_and_inference_diagnostic(self):
        series=synthetic_ar1()
        self.assertEqual(len(series),160)
        self.assertGreater(autocorrelation(series),0.20)
        self.assertGreater(iid_mean_se(series),0.)
        self.assertGreater(hac_mean_se(series,4),0.)
        self.assertEqual(len(circular_block_ci(series)),2)
        self.assertLess(circular_block_ci(series)[0],circular_block_ci(series)[1])

    def test_block_bootstrap_is_deterministic_and_rejects_bad_block(self):
        series=synthetic_ar1(n=80,break_at=50)
        self.assertEqual(circular_block_ci(series,block=4,seed=22,n_boot=200),
                         circular_block_ci(series,block=4,seed=22,n_boot=200))
        with self.assertRaises(ValueError):
            circular_block_ci(series,block=81)
        with self.assertRaises(ValueError):
            hac_mean_se(series,lags=len(series))

    def test_changing_later_period_does_not_change_earlier_statistics(self):
        series=synthetic_ar1()
        changed=list(series)
        changed[-1]+=999.
        self.assertEqual(series[:100],changed[:100])
        self.assertEqual(hac_mean_se(series[:100],3),
                         hac_mean_se(changed[:100],3))

    def test_pre_post_2026_warning_limit_changes_on_both_exchanges(self):
        for venue in ("SSE","SZSE"):
            old=trading_rule(venue,"MAIN","2026-07-03",risk_warning=True)
            new=trading_rule(venue,"MAIN","2026-07-06",risk_warning=True)
            self.assertEqual(old["price_limit_pct"],.05)
            self.assertEqual(new["price_limit_pct"],.10)
            self.assertIn("2026",new["reference_url"])

    def test_board_specific_price_bands(self):
        expected={("SSE","MAIN"):.10,("SSE","STAR"):.20,
                  ("SZSE","MAIN"):.10,("SZSE","GEM"):.20,
                  ("BSE","STOCK"):.30}
        for key,price in expected.items():
            with self.subTest(board=key):
                self.assertEqual(trading_rule(*key,"2026-07-06")["price_limit_pct"],price)

    def test_ipo_exemptions_require_explicit_session_index(self):
        for venue,board,last in (("SSE","MAIN",5),("SZSE","GEM",5),
                                 ("BSE","STOCK",1)):
            rule=trading_rule(venue,board,"2026-08-10",ipo_session=last)
            self.assertIsNone(rule["price_limit_pct"])
            self.assertEqual(rule["price_band_exemption"],"VERIFIED_IPO_SESSION")
            final=trading_rule(venue,board,"2026-08-10",ipo_session=last+1)
            self.assertIsNotNone(final["price_limit_pct"])
        with self.assertRaises(ValueError):
            trading_rule("SSE","STAR","2026-08-10",ipo_session=0)

    def test_buy_lot_differs_star_and_main(self):
        main=trading_rule("SZSE","MAIN","2026-08-10")
        star=trading_rule("SSE","STAR","2026-08-10")
        bse=trading_rule("BSE","STOCK","2026-08-10")
        self.assertTrue(validate_buy_size(main,100))
        self.assertFalse(validate_buy_size(main,101))
        self.assertFalse(validate_buy_size(star,199))
        self.assertTrue(validate_buy_size(star,201))
        self.assertTrue(validate_buy_size(bse,101))
        self.assertFalse(validate_buy_size(bse,99))

    def test_price_band_is_not_execution_certificate(self):
        old=trading_rule("SSE","MAIN","2025-03-03",risk_warning=True)
        new=trading_rule("SSE","MAIN","2026-07-06",risk_warning=True)
        self.assertEqual(price_band(old,"10")["upper"],"10.50")
        self.assertEqual(price_band(new,"10")["upper"],"11.00")
        self.assertIn("NOT_EXECUTION", price_band(new,"10")["meaning"])
        with self.assertRaises(ValueError):
            price_band(new,"0")

    def test_no_unsupported_silent_rule_fallback(self):
        for args in (("BSE","STOCK","2025-07-01"),
                     ("SSE","MAIN","2020-01-01"),
                     ("SSE","ETF","2026-09-01"),
                     ("SZSE","GEM","2026-09-01")):
            if args[1]=="GEM":
                with self.assertRaisesRegex(ValueError,"non-main"):
                    trading_rule(*args,risk_warning=True)
            else:
                with self.assertRaises(ValueError):
                    trading_rule(*args)

    def test_cross_time_zone_gate_handles_us_closes(self):
        china="2026-11-13T18:00:00+08:00"
        self.assertTrue(known_before_decision("2026-11-12T16:00:00-05:00",china))
        self.assertFalse(known_before_decision("2026-11-13T16:00:00-05:00",china))
        with self.assertRaisesRegex(ValueError,"timezone"):
            known_before_decision("2026-11-13T16:00:00",china)

    def test_exchange_calendar_does_not_guess_holidays(self):
        calendar=["2026-09-30","2026-10-09","2026-10-12"]
        self.assertEqual(next_session(calendar,"2026-09-30"),"2026-10-09")
        with self.assertRaisesRegex(ValueError,"sorted"):
            next_session(calendar[::-1],"2026-09-30")
        with self.assertRaisesRegex(ValueError,"later"):
            next_session(calendar,"2026-10-12")


if __name__ == "__main__":
    unittest.main()
