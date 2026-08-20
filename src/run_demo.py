"""运行合成数据端到端示例：python -m src.run_demo"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .research import run_research
from .run_utils import prepare_run_directory
from .synthetic_data import build_features_and_labels, make_synthetic_panel


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "config" / "research_config.yaml").read_text(encoding="utf-8"))
    data_cfg = {k: v for k, v in config["data"].items() if k != "min_history"}
    min_history = int(config["data"].get("min_history", 1))
    panel = make_synthetic_panel(seed=config["seed"], **data_cfg)
    sample = build_features_and_labels(
        panel, horizon=config["label"]["horizon"], min_history=min_history
    )
    output = prepare_run_directory(root / config["output_dir"])
    (output / "data_source.json").write_text(
        json.dumps({"type": "synthetic", "parameters": data_cfg, "seed": config["seed"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    sample.to_csv(output / "sample.csv", index=False)
    metrics = run_research(sample, config, output)
    print(f"sample rows: {len(sample):,}")
    print(f"out-of-sample folds: {len(metrics['folds'])}")
    for model, result in metrics["models"].items():
        print(f"{model}: mean RankIC={result['mean_rank_ic']:.4f}, total return={result['backtest'].get('total_return', 0):.2%}")
    print(f"results: {output}")


if __name__ == "__main__":
    main()
