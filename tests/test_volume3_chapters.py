"""Editorial and data-boundary checks for Volume III written chapters 01–07 and 09–10.

Proves textbook structure and consistency, NOT independent real-market performance.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

from reader.build_reader import collect_documents, collect_framework_documents
from examples.volume3_strategy_lab import load_fixture, evaluate
from examples.volume3_execution_replay_lab import load_fixture as load_execution_fixture, evaluate as evaluate_execution

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "advanced/volume-3"
NEW = (
    "01_strategy_contract", "02_market_regime",
    "03_industry_rotation", "04_reversal_momentum",
)


class ThirdVolumeChaptersTests(unittest.TestCase):
    def test_first_four_have_full_ordered_chapters_exercises_and_no_draft(self):
        for n, slug in enumerate(NEW, 1):
            page = (V3 / (slug + ".md")).read_text("utf-8")
            with self.subTest(chapter=slug):
                self.assertTrue(page.startswith(f"# 第三卷 · {n:02d}｜"))
                self.assertIn("状态：教学正文 v1", page)
                self.assertIn("python examples/volume3_strategy_lab.py --json", page)
                self.assertTrue("习题" in page or "练习" in page)
                self.assertIn("答", page)
                self.assertNotIn("正文待写", page)
                self.assertNotIn("实验未运行", page)
                headings = [int(x) for x in re.findall(r"(?m)^## (\d+)\. ", page)]
                self.assertEqual(headings, list(range(1, 9)))
                self.assertEqual(page.count(r"\["), page.count(r"\]"))
                self.assertEqual(page.count(r"\("), page.count(r"\)"))
                self.assertIn("返回 [本卷目录](README.md)", page)
                self.assertIn("SYNTHETIC_ONLY" if n == 4 else "人工", page)

    def test_local_links_exist_without_external_private_dependencies(self):
        docs = [V3 / (slug + ".md") for slug in NEW] + [V3 / "05_microcap_quality.md", V3 / "06_corporate_events.md", V3 / "07_theme_network.md", V3 / "09_l2_auction.md", V3 / "10_execution_replay.md", V3 / "11_dynamic_alloc.md", V3 / "12_live_system.md", V3 / "13_capstone.md", V3 / "README.md"]
        checked = 0
        for doc in docs:
            body = doc.read_text("utf-8")
            for phrase in ("PTradePolicy", "xc_tushare_data.duckdb",
                           "local_all_a_2024_aggregate.json", "E:/duckdb_data"):
                self.assertNotIn(phrase, body)
            for m in re.finditer(r"\[[^\]]+\]\(([^)\s]+)\)", body):
                href = unquote(m.group(1)).split("#", 1)[0]
                if not href or href.startswith(("https://", "http://", "mailto:")):
                    continue
                target = (doc.parent / href).resolve()
                with self.subTest(page=doc.name, href=href):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), f"Broken third-volume link: {href}")
                checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_textbook_datasets_include_ninth_synthetic_execution_fixture(self):
        manifest = json.loads((ROOT / "data/teaching/manifest.json").read_text("utf-8"))
        self.assertEqual(len(manifest["datasets"]), 9)
        names = [x["id"] for x in manifest["datasets"]]
        self.assertIn("volume3-weekly-synthetic-v1", names)
        self.assertIn("volume3-events-synthetic-v1", names)
        self.assertIn("volume3-theme-network-synthetic-v1", names)
        self.assertIn("volume3-l2-synthetic-v1", names)
        self.assertIn("volume3-execution-synthetic-v1", names)
        payload = load_fixture()
        self.assertEqual(payload["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertEqual(payload["week_count"], 16)
        self.assertEqual(payload["industries_per_week"], 4)
        self.assertEqual(payload["stocks_per_week"], 8)
        self.assertEqual(payload["calendar"], "ARTIFICIAL_PERIOD_SEQUENCE_NO_EXCHANGE_CALENDAR")
        self.assertEqual({w["taxonomy_version"] for w in payload["weeks"]},
                         {"TEACH_OLD", "TEACH_NEW"})
        execution = load_execution_fixture()
        execution_result = evaluate_execution(execution)
        self.assertEqual(execution["expected_order_plans"], 5)
        self.assertEqual(execution_result["evidence_grade"], "SYNTHETIC_ONLY")
        self.assertFalse(execution_result["claims"]["real_market_execution_proven"])
        self.assertFalse(execution_result["claims"]["real_fill_probability_calibrated"])
        self.assertEqual(len(execution_result["execution_outcomes"]), 12)

    def test_course_lab_does_not_pretend_real_pit_oos_or_execution(self):
        result = evaluate(load_fixture())
        self.assertEqual(result["source_kind"], "SYNTHETIC_ONLY")
        self.assertFalse(result["market_pit_proven"])
        self.assertFalse(result["real_market_OOS_proven"])
        self.assertFalse(result["execution_proven"])
        self.assertEqual(result["weeks"], 16)
        self.assertEqual(result["unknown_members"], 1)
        self.assertEqual(result["eligible_training_week_ids_at_week_3"], [1])
        self.assertTrue(result["strategies"]["cash"]["summary"]["all"]
                        ["mean_synthetic_net_proxy"] == 0)

    def test_shelf_and_existing_reading_paths_preserved(self):
        first = collect_documents()
        all_docs = collect_framework_documents()
        self.assertEqual(len(first), 22)
        self.assertEqual(len(all_docs), 33)
        third_chapters = [x for x in all_docs if
                          re.fullmatch(r"advanced/volume-3/\d{2}_[^/]+\.md", x["path"])]
        self.assertEqual(len(third_chapters), 13)
        for n, item in enumerate(third_chapters[:4], 1):
            self.assertTrue(item["title"].startswith(f"第 {n:02d} 章｜"))
            self.assertIn("状态：教学正文 v1", item["content"])
        self.assertTrue("状态：真实价格教学案例 v1" in
                        third_chapters[7]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[4]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[5]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[6]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[8]["content"])
        self.assertIn("状态：教学正文 v1", third_chapters[9]["content"])
        self.assertIn("volume3_execution_replay_lab.py --json", third_chapters[9]["content"])
        self.assertIn("SYNTHETIC_ONLY", third_chapters[9]["content"])
        self.assertIn("QMT Tick", third_chapters[8]["content"])
        self.assertIn("SYNTHETIC_ONLY", third_chapters[8]["content"])

    def test_reader_completion_respects_existing_storage_and_new_written_chapters(self):
        app = (ROOT / "reader/app.js").read_text("utf-8")
        self.assertIn('const STORAGE_KEY = "quant-learning-reader-v1"', app)
        self.assertIn('12 章教学正文 · 1 章入门案例', app)
        self.assertIn("0[1-7]|08|09|10|1[1-3]", app)
        self.assertIn("readingRoute = firstVolume.filter", app)
        self.assertNotIn('status: "1 章案例初稿 · 12 章待写"', app)


class CapstoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from examples.volume3_capstone_lab import report
        cls.r = report()

    def test_caps_future_isolation_and_accounting(self):
        from examples.volume3_capstone_lab import make_panel, allocation_at, POLICY
        panel = make_panel()
        old = allocation_at(panel,110)
        for row in panel.values():
            row["close"][111:] = [999.] * len(row["close"][111:])
        self.assertEqual(old,allocation_at(panel,110))
        for d in self.r["allocation"]["decisions"]:
            self.assertAlmostEqual(sum(d["fixed"].values()),.95)
            self.assertAlmostEqual(sum(d["budgets"].values()),1.)
            self.assertLessEqual(sum(d["risk"].values()),.95+1e-10)
            self.assertLessEqual(d["estimated_vol"],POLICY["daily_vol_target"]+1e-12)
            for g in range(5):
                self.assertLessEqual(sum(w for k,w in d["risk"].items()
                                         if panel[k]["industry"]==g),.30+1e-10)
            self.assertTrue(all(0<=w<=.15+1e-10 for w in d["risk"].values()))
        for a in self.r["allocation"]["attribution"].values():
            self.assertTrue(all(abs(d["residual"])<1e-6 for d in a["daily"]))
        self.assertEqual(self.r["allocation"]["accounts"]["cash"]["final_nav"],1_000_000)

    def test_reservations_timeout_restart_and_fill_conflict(self):
        from examples.volume3_capstone_lab import PaperLedger, broker_view
        l = PaperLedger()
        self.assertEqual(l.submit("x","S01","BUY",200,1000,1,1),"ACCEPTED")
        self.assertEqual(l.reserved_cash(),200000)
        self.assertEqual(l.fill("f","x",100,990),"APPLIED")
        self.assertEqual(l.s["cash"],901000)
        self.assertEqual(l.reserved_cash(),100000)
        l.timeout("x")
        l=PaperLedger(l.snapshot())
        self.assertEqual(l.submit("x","S01","BUY",200,1000,1,1),"DUPLICATE")
        self.assertEqual(l.fill("f","x",100,990),"DUPLICATE")
        self.assertEqual(l.s["cash"],901000)
        self.assertFalse(l.resume(broker_view(l),True,1))
        self.assertEqual(l.fill("f","x",100,991),"CONFLICT")
        self.assertEqual(l.s["cash"],901000)
        l.cancel_confirmed("x")
        self.assertEqual(l.reserved_cash(),0)
        self.assertTrue(l.resume(broker_view(l),True,1))
        self.assertEqual(l.submit("sell","S01","SELL",100,1000,1,1),"T_PLUS_ONE_OR_RESERVED")
        l.next_session()
        self.assertEqual(l.submit("sell","S01","SELL",100,1000,2,2),"ACCEPTED")
        self.assertEqual(l.submit("sell2","S01","SELL",100,1000,2,2),"T_PLUS_ONE_OR_RESERVED")
        self.assertEqual(l.fill("f2","sell",100,1010),"APPLIED")
        self.assertEqual(l.s["cash"],1002000)

    def test_gate_cannot_convert_synthetic_to_live(self):
        from examples.volume3_capstone_lab import gate_decision,digest,report
        r=self.r
        self.assertEqual(r["decision"],"RESEARCH_ONLY")
        self.assertTrue(r["gates"]["ledger_reconciled"])
        self.assertTrue(r["gates"]["fault_drill"])
        self.assertFalse(r["gates"]["real_pit"])
        self.assertFalse(r["gates"]["independent_oos"])
        self.assertFalse(r["gates"]["real_execution"])
        self.assertFalse(r["gates"]["production_approval"])
        self.assertEqual(gate_decision(dict(r["gates"],fault_drill=False)),"STOP_AND_REPAIR")
        self.assertEqual(gate_decision({k:True for k in r["gates"]}),"ELIGIBLE_FOR_HUMAN_REVIEW")
        self.assertEqual(digest({k:v for k,v in r.items() if k!="report_sha256"}),r["report_sha256"])
        self.assertEqual(report()["report_sha256"],r["report_sha256"])


if __name__ == "__main__":
    unittest.main()
