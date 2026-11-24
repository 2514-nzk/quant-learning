"""Volume II internal teaching-quality gates; not market verification."""
from __future__ import annotations
import math
import re
import unittest
from pathlib import Path
from urllib.parse import unquote
from examples.advanced_pit_intake_lab import demo_payload, evaluate

ROOT = Path(__file__).resolve().parents[1]
VOL = ROOT / "advanced" / "volume-2"
CHAPTERS = (
    "01_research_protocol", "02_math_statistics", "03_time_series",
    "04_market_rules", "05_pit_data", "06_labels_splits",
    "07_factor_engineering", "08_factor_validation",
    "09_factor_combination", "10_machine_learning", "11_oos_drift",
    "12_portfolio_optimization", "13_backtest_execution",
    "14_reproducible_capstone",
)
QA_STATUS = "状态：教学版 v1 方法与例题内部校审完成"

class VolumeTwoQualityGate(unittest.TestCase):
    def read(self, slug):
        return (VOL / (slug + ".md")).read_text(encoding="utf-8")

    def test_exactly_fourteen_ordered_chapters(self):
        actual = {p.stem for p in VOL.glob("[0-9][0-9]_*.md")}
        self.assertEqual(actual, set(CHAPTERS))
        for number, slug in enumerate(CHAPTERS, 1):
            body = self.read(slug)
            with self.subTest(chapter=slug):
                self.assertRegex(body, rf"(?m)^# 第二卷 · {number:02d}｜")
                headings = [int(x) for x in re.findall(
                    r"(?m)^## (\d+)\. ", body)]
                self.assertTrue(headings)
                self.assertEqual(headings, list(range(1, max(headings) + 1)))
                self.assertIn(QA_STATUS, body)
                self.assertEqual(body.count("### 质量核对｜"), 1)
                self.assertIn("答", body)
                self.assertIn("python examples/", body)
                self.assertRegex(body, r"返回 \[[^\]]*目录\]\(README\.md\)")

    def test_math_delimiters_and_fences_are_well_formed(self):
        for slug in CHAPTERS:
            body = self.read(slug)
            with self.subTest(chapter=slug):
                self.assertEqual(body.count(r"\["), body.count(r"\]"))
                self.assertEqual(body.count(r"\("), body.count(r"\)"))
                self.assertNotRegex(body, r"(?m)^\[$")
                self.assertNotRegex(body, r"(?m)^N_t\^\{reference\}=#")
                fences = [line for line in body.splitlines()
                          if line.startswith("~~~")]
                self.assertEqual(len(fences) % 2, 0)

    def test_introductory_math_is_typeset_and_explained(self):
        intro = self.read("01_research_protocol")
        self.assertNotIn("IC_t = Spearman", intro)
        for token in (r"\operatorname{Spearman}", r"H_0:\quad E[IC_t]=0",
                      r"H_1:\quad E[IC_t]>0", "因子名次", "收益名次",
                      "样本平均", "完整的单侧原假设"):
            self.assertIn(token, intro)
        chapter = self.read("02_math_statistics")
        self.assertLess(chapter.index("阅读准备｜先认识这些数学符号"),
                        chapter.index("## 1. 概率论"))
        self.assertIn("70 ÷ 250 = 28%", chapter)
        self.assertIn("0.20 ÷ 10 = 0.02", chapter)
        self.assertAlmostEqual(1 - 6 * (0 + 1 + 1 + 0) / (4 * (4**2 - 1)), .8)
        self.assertAlmostEqual((.12 - .04 + .06 + .02 + .09) / 5, .05)

    def test_local_markdown_code_and_data_links_exist(self):
        source_files = [VOL / (c + ".md") for c in CHAPTERS] + [
            VOL / "README.md", VOL / "REVIEW_BACKLOG.md",
            VOL / "QUALITY_REVIEW_V1.md",
            VOL / "HISTORICAL_UNIVERSE_SOURCE_AUDIT.md",
        ]
        checked = 0
        for page in source_files:
            for m in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)",
                                 page.read_text("utf-8")):
                link = unquote(m.group(1)).split("#", 1)[0]
                if not link or link.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (page.parent / link).resolve()
                with self.subTest(page=page.name, link=link):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f"broken link: {link}")
                checked += 1
        self.assertGreaterEqual(checked, 80)

    def test_no_private_research_dependency_in_book(self):
        pages = [VOL / (c + ".md") for c in CHAPTERS] + [
            VOL / "README.md", VOL / "REVIEW_BACKLOG.md",
            VOL / "QUALITY_REVIEW_V1.md",
            VOL / "HISTORICAL_UNIVERSE_SOURCE_AUDIT.md",
        ]
        forbidden = ("PTradePolicy", "xc_tushare_data.duckdb",
                     "local_all_a_2024_aggregate.json",
                     "advanced_source_join_probe.py",
                     "E:/duckdb_data", "E:\\duckdb_data")
        for page in pages:
            text = page.read_text("utf-8")
            with self.subTest(page=page.name):
                for needle in forbidden:
                    self.assertNotIn(needle, text)

    def test_pit_example_matches_frozen_course_fixture(self):
        report = evaluate(demo_payload())
        self.assertEqual(report["membership_asof"]["A"], "ELIGIBLE")
        self.assertEqual(report["membership_asof"]["B"],
                         "UNKNOWN_NO_KNOWN_MEMBERSHIP")
        self.assertEqual(report["membership_asof"]["C"], "INELIGIBLE")
        self.assertEqual(report["facts_asof"]["A"]["roe"]["value"], 0.10)
        self.assertEqual((report["train_labels_eligible"],
                          report["train_labels_purged"]), (1, 1))
        self.assertFalse(report["historical_pit_proven"])
        chapter = self.read("05_pit_data")
        for token in ("2024-03-15 16:20", "2024-04-10 16:20",
                      "2024-03-25 16:30", "NOT_COLLECTED", "0.10", "0.15"):
            self.assertIn(token, chapter)

    def test_topk_real_comparison_and_buffer_arithmetic(self):
        import json
        from statistics import mean
        rounds = json.loads((ROOT / "data/real_a_share/teaching_case.json").read_text("utf-8"))["rounds"]
        for k, expected, replacements in (
            (1, .21982881609262006, 12),
            (2, .14858672505471504, 19),
            (3, .03472348072185749, 15),
            (4, .12881197772689168, 0),
        ):
            selected = [sorted(r["rows"], key=lambda x: (-x["mom5"], x["symbol"]))[:k] for r in rounds]
            self.assertAlmostEqual(math.prod(1 + mean(x["forward_return"] for x in q) for q in selected)-1, expected)
            sets = [{x["symbol"] for x in q} for q in selected]
            self.assertEqual(sum(len(b-a) for a,b in zip(sets,sets[1:])), replacements)
        old = set("ABC")
        for new, count in ((set("DEF"),3),(set("ADE"),2),(set("ABD"),1)):
            self.assertEqual(len(new-old),count)
            self.assertAlmostEqual(sum(abs((i in new)/3-(i in old)/3) for i in old|new),2*count/3)
        self.assertAlmostEqual(.9*.98/(.98+.82),.49)
        self.assertAlmostEqual(.9*.82/(.98+.82),.41)
        last = rounds[-1]["rows"]
        mom = sorted(last,key=lambda r:-r["mom5"])
        bias = sorted(last,key=lambda r:-(r["signal_close"]/r["ma5"]-1))
        points = {}
        for seq in (mom,bias):
            for j,row in enumerate(seq):
                points[row["symbol"]] = points.get(row["symbol"],0)+(4-j)/2
        self.assertEqual(points,{"688256":4,"300750":2.5,"002594":2.5,"600519":1})
        self.assertEqual(sorted(points,key=lambda code:(-points[code],code))[:2],["688256","002594"])


    def test_real_four_stock_editorial_examples(self):
        import json
        from statistics import mean, stdev
        from examples.real_stock_learner import rank_ic
        rounds = json.loads((ROOT / "data/real_a_share/teaching_case.json").read_text("utf-8"))["rounds"]
        ics, tops, bottoms, eqs = [], [], [], []
        selected_up = total_up = 0
        for period in rounds:
            rows = sorted(period["rows"], key=lambda r: -r["mom5"])
            ics.append(rank_ic(rows))
            tops.append(mean(r["forward_return"] for r in rows[:2]))
            bottoms.append(mean(r["forward_return"] for r in rows[2:]))
            eqs.append(mean(r["forward_return"] for r in rows))
            selected_up += sum(r["forward_return"] > 0 for r in rows[:2])
            total_up += sum(r["forward_return"] > 0 for r in rows)
        self.assertEqual(len(rounds), 18)
        self.assertEqual((selected_up, total_up), (20, 39))
        self.assertAlmostEqual(mean(ics), -.1222222222)
        self.assertAlmostEqual(stdev(ics), .5906681716)
        self.assertAlmostEqual(mean(ics)/stdev(ics), -.2069219709)
        self.assertAlmostEqual(math.prod(1+r for r in tops)-1, .1485867251)
        self.assertAlmostEqual(math.prod(1+r for r in bottoms)-1, .0958808286)
        self.assertAlmostEqual(math.prod(1+r for r in eqs)-1, .1288119777)
        j = next(i for i, r in enumerate(rounds) if r["signal_date"] == "2024-01-23")
        self.assertAlmostEqual(ics[j], -.2)
        self.assertAlmostEqual(tops[j]-eqs[j], .0118989615)

    def test_real_time_series_and_execution_examples(self):
        import csv
        import json
        from statistics import mean
        from examples.real_stock_learner import rank_ic
        rounds = json.loads((ROOT / "data/real_a_share/teaching_case.json").read_text("utf-8"))["rounds"]
        ics = [rank_ic(r["rows"]) for r in rounds]
        u = [v-mean(ics) for v in ics]
        def ac(k):
            return sum(u[i]*u[i-k] for i in range(k,len(u)))/len(u)
        self.assertAlmostEqual(ac(1)/ac(0), -.2805253736)
        self.assertAlmostEqual(math.sqrt((ac(0)+2*(2/3*ac(1)+1/3*ac(2)))/len(u)), .0751651470)
        with (ROOT / "data/real_a_share/688256.csv").open(encoding="utf-8") as f:
            bars = {r["trade_date"]: r for r in csv.DictReader(f)}
        self.assertEqual(float(bars["2024-02-08"]["close"]),115.4)
        self.assertEqual(float(bars["2024-02-19"]["open"]),124.2)
        self.assertEqual(math.floor(100000/124.2),805)
        self.assertAlmostEqual(float(bars["2024-06-28"]["close"])/float(bars["2024-06-24"]["open"])-1,-.0750931099,places=8)
        self.assertEqual(rounds[-1]["exit_date"],"2024-06-28")
        self.assertLess(rounds[-1]["signal_date"],"2024-06-25")
        self.assertGreater(rounds[-1]["exit_date"],"2024-06-25")


    def test_real_factor_cross_section_and_dividend_example(self):
        import csv
        import json
        files = {code: ROOT / "data" / "real_a_share" / (code + ".csv")
                 for code in ("300750", "600519", "688256", "002594")}
        returns = {}
        closes = {}
        for code, path in files.items():
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_date = {row["trade_date"]: row for row in rows}
            ix = next(i for i, row in enumerate(rows)
                      if row["trade_date"] == "2024-06-21")
            returns[code] = {
                n: float(rows[ix]["close"]) / float(rows[ix-n]["close"]) - 1
                for n in (5, 20, 60)
            }
            closes[code] = by_date
        self.assertAlmostEqual(returns["600519"][5], -.0540192926, places=8)
        self.assertAlmostEqual(returns["688256"][20], .1719651606, places=8)
        self.assertAlmostEqual(returns["002594"][60], .1448732587, places=8)
        raw = float(closes["600519"]["2024-06-21"]["close"]) / float(closes["600519"]["2024-06-14"]["close"]) - 1
        dividend_total = (float(closes["600519"]["2024-06-21"]["close"]) + 30.876) / float(closes["600519"]["2024-06-14"]["close"]) - 1
        self.assertAlmostEqual(raw, -.0540192926, places=8)
        self.assertAlmostEqual(dividend_total, -.0341633441, places=8)
        with (ROOT / "data/real_a_share/688256.csv").open(encoding="utf-8") as f:
            cambricon = {r["trade_date"]: r for r in csv.DictReader(f)}
        prior_close = float(cambricon["2024-02-08"]["close"])
        next_open = float(cambricon["2024-02-19"]["open"])
        self.assertAlmostEqual(prior_close, 115.40)
        self.assertAlmostEqual(next_open, 124.20)
        self.assertAlmostEqual(next_open / prior_close - 1, .0762564991, places=8)
        self.assertEqual(int(100000 / prior_close), 866)
        self.assertEqual(int(100000 / next_open), 805)

        def ranks(values):
            order = sorted(range(len(values)), key=lambda i: values[i])
            result = [0] * len(values)
            for rank, index in enumerate(order, 1):
                result[index] = rank
            return result

        def spearman(x, y):
            rx, ry = ranks(x), ranks(y)
            mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
            cov = sum((u-mx)*(v-my) for u,v in zip(rx,ry))
            sx = sum((u-mx)**2 for u in rx) ** .5
            sy = sum((v-my)**2 for v in ry) ** .5
            return cov / (sx*sy)

        order = list(files)
        self.assertAlmostEqual(spearman([returns[c][5] for c in order],
                                        [returns[c][20] for c in order]), .8)
        self.assertAlmostEqual(spearman([returns[c][20] for c in order],
                                        [returns[c][60] for c in order]), 1.0)
        import itertools
        possible = {
            round(1 - 6 * sum((i+1-p[i])**2 for i in range(4)) / 60, 1)
            for p in itertools.permutations(range(1,5))
        }
        self.assertEqual(possible, {i/5 for i in range(-5,6)})
        case = json.loads((ROOT / "data" / "real_a_share" / "teaching_case.json").read_text("utf-8"))
        self.assertEqual(len(case["rounds"]), 18)
        self.assertEqual(sum(len(period["rows"]) for period in case["rounds"]), 72)
        self.assertEqual(18 * (4*3//2), 108)

    def test_worked_example_math(self):
        self.assertAlmostEqual(.7 * .1 / (.7 * .1 + .2 * .9), .28)
        self.assertAlmostEqual((4 / 3) / (2 / 3 + 1), .8)
        self.assertAlmostEqual(math.sqrt((.25 - .1875) / 4), .125)
        self.assertAlmostEqual(math.sqrt(1 / 3) / 2, .288675134594813)
        self.assertAlmostEqual(.4 * .08 + .4 * .12 -
                               (.4**2 * .04 + .4**2 * .09), .0592)
        after_buy = 10000 - 100 * 10 - 5
        self.assertEqual(after_buy, 8995)
        self.assertEqual(after_buy + 100 * 10.2, 10015)
        self.assertAlmostEqual(after_buy + 100 * 10.2 - 5 -
                               .001 * 100 * 10.2, 10008.98)

    def test_rules_and_teaching_versus_research_evidence(self):
        rules = self.read("04_market_rules")
        for token in ("2026-04-24", "2026-07-06", "3.7.1–3.7.10",
                      "www.sse.com.cn", "www.szse.cn", "www.bse.cn"):
            self.assertIn(token, rules)
        quality = (VOL / "QUALITY_REVIEW_V1.md").read_text("utf-8")
        for token in ("14/14", "不代表独立外部同行评审", "真实四股",
                      "SYNTHETIC_ONLY"):
            self.assertIn(token, quality)
        index = (VOL / "README.md").read_text("utf-8")
        self.assertEqual(index.count("教学版 v1 / 实验可复算"), 14)
        self.assertIn("(QUALITY_REVIEW_V1.md)", index)
        self.assertIn("14 章教学版 v1",
                      (ROOT / "README.md").read_text("utf-8"))

    def test_public_reader_labels_not_stale(self):
        html = (ROOT / "reader/index.html").read_text("utf-8")
        js = (ROOT / "reader/app.js").read_text("utf-8")
        self.assertIn("第二卷 14 章教学版 v1", html)
        self.assertNotIn("第二卷为教学初稿", html)
        self.assertIn("教学版 v1", js)
        self.assertNotIn("初稿试读", js)

class ClassroomResearchTests(unittest.TestCase):
    def test_reproducible_panel_and_no_future_feature(self):
        from examples.rev20_classroom_lab import make_panel, signal_snapshot, report
        panel = make_panel()
        self.assertEqual(len(panel), 40)
        original = signal_snapshot(panel, 20)
        panel["S01"]["close"][21:] = [999.0] * len(panel["S01"]["close"][21:])
        self.assertEqual(original, signal_snapshot(panel, 20))
        r = report()
        self.assertEqual(r, report())
        self.assertEqual(r["source_kind"], "SYNTHETIC_ONLY")
        self.assertEqual(len(r["weeks"]), 24)
        self.assertEqual([w["signal"] for w in r["weeks"]], list(range(20, 136, 5)))
        self.assertNotIn(75, r["trainable_at_first_validation"])
        self.assertIn(70, r["trainable_at_first_validation"])
        self.assertTrue(all(w["label_available"] == w["signal"]+6 for w in r["weeks"]))
        for w in r["weeks"]:
            self.assertEqual(len(w["scores"])+len(w["excluded"]), 40)
            self.assertEqual(len(w["labels"])+len(w["missing_labels"]), w["eligible"])
            if w["missing_labels"]:
                self.assertIsNone(w["gross_difference"])

    def test_pit_split_dividend_and_fee_counterexamples(self):
        from examples.rev20_classroom_lab import pitfalls, spearman, make_panel, signal_snapshot
        p = pitfalls()
        self.assertEqual(p["pit"], {"correct": .10, "wrong_latest": .15})
        self.assertEqual(p["split"]["raw_return"], -.5)
        self.assertEqual(p["split"]["adjusted_return"], 0)
        self.assertEqual(p["split"]["before"], p["split"]["after"])
        self.assertEqual(p["dividend"]["total_return"], 0)
        self.assertEqual(p["blocked_buy"]["filled"], 0)
        self.assertLess(p["fee_example"]["net_pnl"], 0)
        self.assertAlmostEqual(spearman([1,2,3,4], [1,3,2,4]), .8)
        self.assertIsNone(spearman([1,1], [2,3]))
        panel = make_panel()
        self.assertEqual(signal_snapshot(panel, 20)[1]["S39"], "OUTSIDE_LISTING")
        self.assertEqual(signal_snapshot(panel, 55)[1]["S39"], "SHORT_HISTORY")
        self.assertEqual(signal_snapshot(panel, 80)[1]["S38"], "ST_POLICY")
        self.assertEqual(signal_snapshot(panel, 95)[1]["S40"], "OUTSIDE_LISTING")


class IntegratedClassroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from examples.rev20_classroom_lab import extended_report
        cls.result = extended_report()

    def test_selection_freezes_before_holdout_and_purges_late_labels(self):
        r = self.result
        m = r["models"]
        self.assertEqual(m["freeze_at"], 110)
        self.assertEqual(len(m["validation"]), 6)
        self.assertFalse(m["validation"][-1]["selection_eligible"])
        self.assertTrue(m["validation"][-2]["selection_eligible"])
        for item in m["validation"] + m["holdout"]:
            p = item["prediction"]
            self.assertTrue(all(t+6 < p["signal"] for t in p["trained_signals"]))
            self.assertEqual(len(p["beta"]), 3)
        self.assertEqual(len(r["diagnostics"]), 24)

    def test_future_changes_cannot_change_current_prediction_or_frozen_choice(self):
        from examples.rev20_classroom_lab import (make_panel, observe_week, SIGNALS,
                                                  predict_candidates, model_experiment)
        panel = make_panel()
        weeks = [observe_week(panel, t) for t in SIGNALS]
        p = predict_candidates(panel, weeks, 110)
        winner = model_experiment(panel, weeks)["selected"]
        for w in weeks:
            if w["label_available"] >= 110:
                w["labels"] = {k: -100*y+1 for k, y in w["labels"].items()}
        for row in panel.values():
            row["close"][111:] = [1000.] * len(row["close"][111:])
        self.assertEqual(p, predict_candidates(panel, weeks, 110))
        self.assertEqual(winner, model_experiment(panel, weeks)["selected"])

    def test_account_reconciles_each_order_and_each_daily_nav(self):
        from examples.rev20_classroom_lab import make_panel
        panel = make_panel()
        self.assertEqual(set(self.result["accounts"]), {"rev20", "selected", "equal"})
        for variants in self.result["accounts"].values():
            self.assertEqual(set(variants), {"ideal", "cost_only", "constrained"})
            self.assertEqual(variants["ideal"]["fees"], 0)
            self.assertEqual(variants["ideal"]["slippage"], 0)
            self.assertEqual(variants["cost_only"]["targets"], variants["constrained"]["targets"])
            for account in variants.values():
                cash = 1_000_000.
                shares = {}
                by_day = {}
                for order in account["orders"]:
                    by_day.setdefault(order["day"], []).append(order)
                for d in account["daily"]:
                    opening_shares = dict(shares)
                    for o in by_day.get(d["day"], []):
                        self.assertEqual(o["day"], o["decision"]+1)
                        self.assertTrue(0 <= o["filled"] <= o["requested"])
                        self.assertEqual(o["filled"] % 100, 0)
                        k = o["code"]
                        if o["side"] == "BUY":
                            cash -= o["notional"] + o["fee"]
                            shares[k] = shares.get(k, 0)+o["filled"]
                        else:
                            self.assertLessEqual(o["filled"], opening_shares.get(k, 0))
                            opening_shares[k] -= o["filled"]
                            cash += o["notional"] - o["fee"]
                            shares[k] = shares.get(k, 0)-o["filled"]
                        if not shares.get(k):
                            shares.pop(k, None)
                        self.assertAlmostEqual(cash, o["cash_after"], places=6)
                        self.assertGreaterEqual(cash, -1e-6)
                    self.assertEqual(shares, d["holdings"])
                    self.assertAlmostEqual(cash, d["cash"], places=6)
                    self.assertAlmostEqual(cash+sum(q*panel[k]["close"][d["day"]]
                                                    for k,q in shares.items()), d["nav"], places=6)
                self.assertAlmostEqual(account["final_nav"], account["daily"][-1]["nav"])

    def test_blocked_sell_does_not_release_cash(self):
        from examples.rev20_classroom_lab import make_panel, simulate_account, signal_snapshot
        panel = make_panel()
        # S08: day 111 not blocked for buy; day 116+8 is not a sell block.
        # Find an eligible name for which the second order is blocked for selling.
        from examples.rev20_classroom_lab import blocked_side
        code = next(k for k in signal_snapshot(panel, 110)[0]
                    if blocked_side(k, 111) not in ("BUY","BOTH")
                    and blocked_side(k, 116) in ("SELL","BOTH"))
        account = simulate_account(panel, {110:{code:.1},115:{}})
        sell = next(o for o in account["orders"] if o["side"] == "SELL")
        self.assertEqual(sell["filled"], 0)
        self.assertEqual(sell["reason"], "SYNTHETIC_BLOCK")
        self.assertEqual(account["daily"][-1]["holdings"][code],
                         next(o["filled"] for o in account["orders"] if o["side"] == "BUY"))


class RiskClassroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from examples.rev20_classroom_lab import risk_report
        cls.r = risk_report()

    def test_caps_and_time_gate(self):
        from examples.rev20_classroom_lab import make_panel, RISK_TARGET
        panel = make_panel()
        for row in self.r["decisions"]:
            for label in ("risk", "monitored"):
                risk = row[label]
                self.assertLessEqual(risk["scaled_vol"], RISK_TARGET+1e-12)
                self.assertLessEqual(sum(risk["weights"].values()), .95+1e-12)
                self.assertTrue(all(0 <= v <= .15+1e-12 for v in risk["weights"].values()))
                for g in range(5):
                    self.assertLessEqual(sum(v for k,v in risk["weights"].items()
                                             if panel[k]["industry"] == g), .30+1e-12)
            self.assertTrue(all(t+6 < row["signal"] for t in row["monitor"]["known_signals"]))
            self.assertLessEqual(row["monitored"]["exposure"], row["risk"]["exposure"]+1e-12)

    def test_risk_and_monitor_ignore_future(self):
        from examples.rev20_classroom_lab import make_panel, observe_week, SIGNALS, risk_weights, monitor_at
        panel = make_panel()
        weeks = [observe_week(panel,t) for t in SIGNALS]
        scores = weeks[18]["scores"]
        original = risk_weights(panel,110,scores),monitor_at(weeks,110)
        for row in panel.values():
            row["close"][111:] = [999.] * len(row["close"][111:])
        for w in weeks:
            if w["label_available"] >= 110:
                w["rank_ic"] = 1.
        self.assertEqual(original,(risk_weights(panel,110,scores),monitor_at(weeks,110)))

    def test_exact_daily_attribution_and_capacity_control(self):
        r = self.r
        for name, result in r["attribution"].items():
            for d in result["daily"]:
                self.assertAlmostEqual(d["market"]+d["industry"]+d["selection"]+
                                       d["fees"]+d["slippage"],d["actual"],places=6)
            self.assertAlmostEqual(result["totals"]["actual"],
                                   r["accounts"][name]["final_nav"]-1_000_000,places=6)
        for a in r["capacity"].values():
            self.assertEqual(a["targets"],r["accounts"]["risk"]["targets"])
        self.assertEqual(r["capacity"][.05],r["accounts"]["risk"])
        self.assertEqual(set(r["decay"]["mean_ic"]),{1,5,10})
        self.assertEqual(len(r["factor_ic"]),24)
        self.assertTrue(all(abs(v["stock"]+v["cash"]-1)<1e-10
                            for rows in r["exposures"].values() for v in rows))

    def test_dashboard_is_serializable_and_preserves_evidence_boundary(self):
        import json
        from examples.rev20_classroom_lab import dashboard_data
        data = dashboard_data(self.r)
        self.assertEqual(data["source_kind"],"SYNTHETIC_ONLY")
        self.assertEqual(set(data["nav"]),{"fixed","risk","monitored"})
        json.dumps(data,allow_nan=False)


if __name__ == "__main__":
    unittest.main()
