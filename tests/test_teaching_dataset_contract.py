"""Every textbook dataset is packaged locally, with explicit evidence labels."""
from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path

from examples.advanced_pit_intake_lab import demo_payload, evaluate
from reader.build_reader import collect_framework_documents

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/teaching/manifest.json"


class TeachingDatasetContractTests(unittest.TestCase):
    def test_catalog_is_self_contained_and_has_no_personal_db(self):
        c = json.loads(CATALOG.read_text("utf-8"))
        self.assertEqual(c["schema_version"], "course-datasets-v1")
        self.assertFalse(c["requires_external_local_db"])
        self.assertEqual([x["id"] for x in c["datasets"]],
                         ["a-share-real-four-v1", "story-synthetic-v1",
                          "pit-events-synthetic-v1", "volume3-weekly-synthetic-v1"])
        for entry in c["datasets"]:
            self.assertTrue(entry["evidence_grade"])
            self.assertTrue(entry["frozen"])
            for key in ("data_file", "manifest", "data_root"):
                if key in entry:
                    p = Path(entry[key])
                    self.assertFalse(p.is_absolute())
                    self.assertNotIn("..", p.parts)
                    self.assertTrue((ROOT / p).exists())
            for path in entry.get("data_files", []):
                self.assertTrue((ROOT / path).is_file())

    def test_four_a_share_real_source_sha_and_fixed_sample(self):
        record = json.loads((ROOT / "data/real_a_share/manifest.json").read_text("utf-8"))
        self.assertEqual(record["retriever"], "AKShare")
        self.assertEqual(record["adjust"], "none")
        self.assertEqual(len(record["items"]), 4)
        self.assertEqual({x["symbol"] for x in record["items"]},
                         {"600519", "688256", "300750", "002594"})
        for item in record["items"]:
            path = ROOT / item["csv_path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             item["csv_sha256"])
            with path.open(encoding="utf-8", newline="") as f:
                bars = list(csv.DictReader(f))
            self.assertEqual(len(bars), 117)
            self.assertEqual((bars[0]["trade_date"], bars[-1]["trade_date"]),
                             ("2024-01-02", "2024-06-28"))

    def test_story_data_is_not_real_market_and_has_exact_round_universe(self):
        with (ROOT / "data/story/rounds.csv").open(
                encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 240)
        for n in range(1, 61):
            group = [x for x in rows if int(x["round_id"]) == n]
            self.assertEqual({x["code"] for x in group}, {"A", "B", "C", "D"})
            self.assertTrue(all(int(x["feature_available_day"]) <=
                                int(x["signal_day"]) <
                                int(x["entry_day"]) <=
                                int(x["exit_day"]) for x in group))

    def test_fixed_synthetic_pit_fixture_powers_existing_lab(self):
        src = json.loads((ROOT / "data/teaching/pit_events_v1.json").read_text("utf-8"))
        self.assertEqual(src["data_kind"], "SYNTHETIC_DEMONSTRATION")
        self.assertEqual(src, demo_payload())
        result = evaluate(src)
        self.assertEqual(result["membership_asof"]["A"], "ELIGIBLE")
        self.assertEqual(result["membership_asof"]["B"], "UNKNOWN_NO_KNOWN_MEMBERSHIP")
        self.assertEqual(result["facts_asof"]["A"]["roe"]["value"], 0.10)
        self.assertEqual((result["train_labels_eligible"],
                          result["train_labels_purged"]), (1, 1))
        self.assertFalse(result["historical_pit_proven"])

    def test_main_curriculum_no_private_research_dependency(self):
        pages = [ROOT / "data/README.md", ROOT / "data/teaching/README.md",
                 ROOT / "advanced/volume-2/README.md",
                 ROOT / "advanced/volume-2/REVIEW_BACKLOG.md",
                 ROOT / "advanced/volume-2/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md"]
        pages += [ROOT / "advanced/volume-2" / f"{n:02d}_{slug}.md" for n, slug in (
            (5, "pit_data"), (6, "labels_splits"), (7, "factor_engineering"),
            (8, "factor_validation"))]
        for path in pages:
            content = path.read_text("utf-8")
            for forbidden in ("PTradePolicy", "xc_tushare_data.duckdb",
                              "local_all_a_2024_aggregate.json",
                              "advanced_source_join_probe.py",
                              "E:/duckdb_data", "E:\\\\duckdb_data"):
                with self.subTest(file=path.name, forbidden=forbidden):
                    self.assertNotIn(forbidden, content)
        chapters = collect_framework_documents()
        self.assertEqual(len([p for p in chapters if
                              p["path"].startswith("advanced/volume-2/") and
                              p["path"].split("/")[-1][:2].isdigit()]), 14)


if __name__ == "__main__":
    unittest.main()
