"""使用本地只读 DuckDB 快照运行真实数据教学示例。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from .duckdb_data import build_real_features_and_labels, inspect_database, load_market_panel, resolve_snapshot
from .research import run_research
from .run_utils import prepare_run_directory


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    base_config = yaml.safe_load((root / "config" / "research_config.yaml").read_text(encoding="utf-8"))
    data_config = yaml.safe_load((root / "config" / "duckdb_config.yaml").read_text(encoding="utf-8"))
    pointer = os.environ.get("QUANT_DUCKDB_SNAPSHOT", str(data_config["snapshot_pointer"]))
    database = resolve_snapshot(pointer)
    coverage = inspect_database(database)
    print("database:", database)
    print("coverage:", coverage)
    panel = load_market_panel(
        database,
        data_config["start"],
        data_config["end"],
        data_config["max_stocks"],
        data_config["min_observations"],
        data_config["liquidity_lookback"],
    )
    sample = build_real_features_and_labels(
        panel,
        base_config["label"]["horizon"],
        int(base_config["data"].get("min_history", 1)),
    )
    output = prepare_run_directory(root / data_config["output_dir"])
    (output / "data_source.json").write_text(
        json.dumps(
            {"type": "duckdb_snapshot", "database": str(database), "coverage": coverage, "config": data_config},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    sample.to_csv(output / "sample.csv", index=False)
    metrics = run_research(sample, base_config, output)
    print(f"sample rows: {len(sample):,}; codes: {sample['code'].nunique()}; folds: {len(metrics['folds'])}")
    print("warning: historical sector classification is incomplete; labels are cross-sectional return ranks, not industry-neutral returns.")
    print("results:", output)


if __name__ == "__main__":
    main()
