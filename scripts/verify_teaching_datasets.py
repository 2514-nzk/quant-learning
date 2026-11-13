#!/usr/bin/env python3
"""Validate the versioned, repository-owned teaching datasets. No network."""
from __future__ import annotations

import argparse
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), pattern="test_teaching_dataset_contract.py",
        top_level_dir=str(ROOT))
    outcome = unittest.TestResult()
    suite.run(outcome)
    manifest = json.loads((ROOT / "data/teaching/manifest.json").read_text("utf-8"))
    report = {
        "dataset_version": manifest["schema_version"],
        "datasets": [e["id"] for e in manifest["datasets"]],
        "tests_run": outcome.testsRun,
        "failures": len(outcome.failures),
        "errors": len(outcome.errors),
        "verified": outcome.wasSuccessful(),
        "real_market_PIT_proven": False,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(f"Course data verification: {'PASS' if outcome.wasSuccessful() else 'FAIL'} "
              f"({outcome.testsRun} tests)")
    if not outcome.wasSuccessful():
        for test, traceback in outcome.errors + outcome.failures:
            print(test, traceback)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
