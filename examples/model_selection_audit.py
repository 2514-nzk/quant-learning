#!/usr/bin/env python3
"""Inspect the *existing* frozen teaching-model report without retraining.

The script checks selection consistency. It does NOT prove the holdout was
untouched, estimate real trading performance, or choose models from test scores.
Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "story" / "model_results.json"


def select_from_validation(trials: list[dict], family: str, key: str):
    """Preserve original trial order when validation scores tie."""
    choices = [trial for trial in trials if trial["family"] == family]
    if not choices:
        raise ValueError(f"No trials found for {family}")
    for trial in choices:
        for metric in ("train_rank_ic", "validation_rank_ic"):
            if not math.isfinite(trial[metric]):
                raise ValueError(f"Non-finite {family} {metric}")
    best = max(choices, key=lambda item: item["validation_rank_ic"])
    return best["parameter"][key], choices


def audit_model_report(payload: dict) -> dict:
    models = payload["models"]
    split = models["split"]
    if split != {"train": [1, 36], "validation": [37, 46], "test": [47, 60]}:
        raise ValueError("Unexpected teaching fold boundaries")
    trials = models["trials"]
    alpha, ridge = select_from_validation(trials, "Ridge", "alpha")
    depth, forest = select_from_validation(trials, "RandomForest", "max_depth")
    if alpha != models["chosen"]["ridge_alpha"]:
        raise ValueError("Ridge was not selected by validation RankIC")
    if depth != models["chosen"]["forest_depth"]:
        raise ValueError("Random forest was not selected by validation RankIC")
    best_iteration = models["chosen"]["lightgbm_iteration_by_validation_l2"]
    if not isinstance(best_iteration, int) or not 1 <= best_iteration <= 200:
        raise ValueError("Invalid LightGBM best iteration")

    # LightGBM used validation *loss* for early stopping, not the three
    # pre-specified trial RankIC values. Those trials do not independently
    # identify best_iteration; we check only its recorded range.
    tested = models["test"]
    if set(tested) != {"momentum", "equal_rank", "Ridge", "RandomForest", "LightGBM"}:
        raise ValueError("Unexpected test comparison set")
    for name, values in tested.items():
        for key in ("mean_rank_ic", "final_money"):
            if not math.isfinite(values[key]):
                raise ValueError(f"Invalid test {key}: {name}")

    return {
        "data_kind": payload["data_kind"],
        "split": split,
        "selection_only_used": "validation_rank_ic for Ridge/RandomForest; validation L2 for LightGBM early stopping",
        "ridge_candidates": ridge,
        "forest_candidates": forest,
        "chosen": models["chosen"],
        "test_descriptive_only": {
            name: {
                "mean_rank_ic": values["mean_rank_ic"],
                "final_money": values["final_money"],
            }
            for name, values in tested.items()
        },
        "caveat": (
            "Consistency audit of a saved report; cannot independently prove "
            "that test data were not inspected in other experiments."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REFERENCE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    with args.report.open(encoding="utf-8") as stream:
        summary = audit_model_report(json.load(stream))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
        return
    print("教学模型选择协议：R01–36 训练 / R37–46 验证 / R47–60 测试")
    for family, trials in (
        ("Ridge", summary["ridge_candidates"]),
        ("RandomForest", summary["forest_candidates"]),
    ):
        print(f"{family}:")
        for trial in trials:
            print(
                f"  {trial['parameter']}: 训练IC={trial['train_rank_ic']:.4f}, "
                f"验证IC={trial['validation_rank_ic']:.4f}"
            )
    print("验证选择：", summary["chosen"])
    print("已经发表在教材中的测试表仅作描述；不得再次据此挑选获胜参数。")
    for name, result in summary["test_descriptive_only"].items():
        print(f"  {name}: IC={result['mean_rank_ic']:.4f}; 期末资金={result['final_money']:.2f}")
    print("注意：只检查报告内部一致性，不代替对训练代码和实验历史的审计。")


if __name__ == "__main__":
    main()
