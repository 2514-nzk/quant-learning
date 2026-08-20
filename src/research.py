"""教学版六层研究流程：数据 -> 配置 -> 训练 -> 预测 -> 回测 -> 评价。"""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from .backtest import top_n_backtest
from .dataset import FEATURES
from .metrics import grouped_returns, rank_ic, summarize_backtest, yearly_backtest_summary

try:
    from lightgbm import LGBMRegressor, early_stopping
except ImportError:  # pragma: no cover - lightgbm 是可选模型
    LGBMRegressor = None
    early_stopping = None


def validate_config(config: dict) -> None:
    required_sections = {"seed", "label", "split", "model"}
    missing = sorted(required_sections - set(config))
    if missing:
        raise ValueError(f"config is missing required sections: {missing}")
    split = config["split"]
    for key in ("train_days", "validation_days", "test_days", "step_days", "embargo_days"):
        if int(split.get(key, 0)) <= 0:
            raise ValueError(f"split.{key} must be positive")
    model = config["model"]
    for key in ("top_n", "holding_days"):
        if int(model.get(key, 0)) <= 0:
            raise ValueError(f"model.{key} must be positive")
    if float(model.get("cost_bps", -1)) < 0 or float(model.get("stress_cost_bps", -1)) < 0:
        raise ValueError("transaction costs cannot be negative")
    if int(config["label"].get("horizon", 0)) != int(model["holding_days"]):
        raise ValueError("label.horizon must equal model.holding_days in the non-overlapping teaching backtest")
    if int(split["embargo_days"]) < int(config["label"]["horizon"]):
        raise ValueError("split.embargo_days must be at least label.horizon")


def rolling_splits(
    dates: list[pd.Timestamp],
    train_days: int,
    validation_days: int,
    test_days: int,
    step_days: int,
    embargo_days: int,
):
    start = train_days
    required = embargo_days + validation_days + embargo_days + test_days
    while start + required <= len(dates):
        train = dates[start - train_days : start]
        validation_start = start + embargo_days
        validation = dates[validation_start : validation_start + validation_days]
        test_start = validation_start + validation_days + embargo_days
        test = dates[test_start : test_start + test_days]
        yield train, validation, test
        start += step_days


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(0)


def _validation_score(frame: pd.DataFrame, predictions: np.ndarray) -> float:
    scored = frame[["trade_date", "label_rank"]].copy()
    scored["prediction"] = predictions
    ic = rank_ic(scored)
    return float(ic.mean()) if not ic.empty else float("-inf")


def _fit_predict(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    config: dict,
) -> tuple[dict[str, np.ndarray], dict[str, dict]]:
    train = train.dropna(subset=["label_rank"])
    validation = validation.dropna(subset=["label_rank"])
    if train.empty or validation.empty:
        raise ValueError("train and validation must contain realized labels")

    x_train, x_validation, x_test = _features(train), _features(validation), _features(test)
    y_train, y_validation = train["label_rank"], validation["label_rank"]
    combined = pd.concat([train, validation], ignore_index=True)
    x_combined, y_combined = _features(combined), combined["label_rank"]
    predictions: dict[str, np.ndarray] = {}
    selection: dict[str, dict] = {}

    ridge_alphas = config["model"].get("ridge_alphas", [config["model"].get("ridge_alpha", 10.0)])
    train_scaler = StandardScaler().fit(x_train)
    ridge_trials = []
    for alpha in ridge_alphas:
        candidate = Ridge(alpha=float(alpha))
        candidate.fit(train_scaler.transform(x_train), y_train)
        score = _validation_score(validation, candidate.predict(train_scaler.transform(x_validation)))
        ridge_trials.append({"alpha": float(alpha), "validation_rank_ic": score})
    best_ridge = max(ridge_trials, key=lambda row: row["validation_rank_ic"])
    final_scaler = StandardScaler().fit(x_combined)
    ridge = Ridge(alpha=best_ridge["alpha"]).fit(final_scaler.transform(x_combined), y_combined)
    predictions["ridge"] = ridge.predict(final_scaler.transform(x_test))
    selection["ridge"] = {"selected": {"alpha": best_ridge["alpha"]}, "trials": ridge_trials}

    rf_default = config["model"]["random_forest"]
    rf_candidates = config["model"].get("random_forest_candidates", [rf_default])
    rf_jobs = int(config["model"].get("n_jobs", -1))
    rf_trials = []
    for params in rf_candidates:
        candidate = RandomForestRegressor(random_state=config["seed"], n_jobs=rf_jobs, **params)
        candidate.fit(x_train, y_train)
        score = _validation_score(validation, candidate.predict(x_validation))
        rf_trials.append({"params": params, "validation_rank_ic": score})
    best_rf = max(rf_trials, key=lambda row: row["validation_rank_ic"])
    rf = RandomForestRegressor(random_state=config["seed"], n_jobs=rf_jobs, **best_rf["params"])
    rf.fit(x_combined, y_combined)
    predictions["random_forest"] = rf.predict(x_test)
    selection["random_forest"] = {"selected": best_rf["params"], "trials": rf_trials}

    if LGBMRegressor is not None:
        lgb_cfg = dict(config["model"]["lightgbm"])
        stopping_rounds = int(lgb_cfg.pop("early_stopping_rounds", 20))
        candidate = LGBMRegressor(
            objective="regression", random_state=config["seed"], n_jobs=rf_jobs, verbosity=-1, **lgb_cfg
        )
        candidate.fit(
            x_train,
            y_train,
            eval_set=[(x_validation, y_validation)],
            eval_metric="l2",
            callbacks=[early_stopping(stopping_rounds=stopping_rounds, verbose=False)],
        )
        best_iteration = int(candidate.best_iteration_ or lgb_cfg["n_estimators"])
        selected_lgb = {**lgb_cfg, "n_estimators": best_iteration}
        final_lgb = LGBMRegressor(
            objective="regression", random_state=config["seed"], n_jobs=rf_jobs, verbosity=-1, **selected_lgb
        )
        final_lgb.fit(x_combined, y_combined)
        predictions["lightgbm"] = final_lgb.predict(x_test)
        selection["lightgbm"] = {
            "selected": selected_lgb,
            "validation_rank_ic": _validation_score(validation, candidate.predict(x_validation)),
            "early_stopping_rounds": stopping_rounds,
        }
    else:
        selection["lightgbm"] = {"skipped": "lightgbm is not installed"}
    return predictions, selection


def _package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _write_manifest(output: Path, config: dict, sample: pd.DataFrame) -> None:
    manifest = {
        "run_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {name: _package_version(name) for name in ("numpy", "pandas", "scikit-learn", "lightgbm")},
        "sample_rows": int(len(sample)),
        "sample_codes": int(sample["code"].nunique()),
        "sample_start": str(sample["trade_date"].min().date()),
        "sample_end": str(sample["trade_date"].max().date()),
        "features": FEATURES,
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "config_used.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def run_research(sample: pd.DataFrame, config: dict, output_dir: str | Path) -> dict:
    validate_config(config)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    sample = sample.copy()
    sample["trade_date"] = pd.to_datetime(sample["trade_date"])
    dates = sorted(sample["trade_date"].unique())
    prediction_rows = []
    split_rows = []
    split_cfg = config["split"]
    for fold, (train_dates, val_dates, test_dates) in enumerate(
        rolling_splits(
            dates,
            split_cfg["train_days"],
            split_cfg["validation_days"],
            split_cfg["test_days"],
            split_cfg["step_days"],
            split_cfg["embargo_days"],
        ),
        1,
    ):
        train = sample[sample.trade_date.isin(train_dates)]
        validation = sample[sample.trade_date.isin(val_dates)]
        test = sample[sample.trade_date.isin(test_dates)]
        if train.empty or validation.empty or test.empty:
            continue
        model_predictions, selection = _fit_predict(train, validation, test, config)
        metadata_columns = [
            "trade_date",
            "code",
            "label_rank",
            "fwd_return",
            "realized_return",
            "ret_1d_forward",
            "can_enter",
            "can_exit_on_schedule",
            "entry_date",
            "scheduled_exit_date",
            "actual_exit_date",
            "exit_delay_days",
        ]
        metadata_columns = [column for column in metadata_columns if column in test]
        for name, values in model_predictions.items():
            part = test[metadata_columns].copy()
            part["model"] = name
            part["prediction"] = values
            part["fold"] = fold
            prediction_rows.append(part)
        split_rows.append(
            {
                "fold": fold,
                "train_start": str(pd.Timestamp(train_dates[0]).date()),
                "train_end": str(pd.Timestamp(train_dates[-1]).date()),
                "validation_start": str(pd.Timestamp(val_dates[0]).date()),
                "validation_end": str(pd.Timestamp(val_dates[-1]).date()),
                "test_start": str(pd.Timestamp(test_dates[0]).date()),
                "test_end": str(pd.Timestamp(test_dates[-1]).date()),
                "selection": selection,
            }
        )

    if not prediction_rows:
        raise ValueError("no rolling split produced predictions; increase data coverage or shorten split windows")
    predictions = pd.concat(prediction_rows, ignore_index=True)
    predictions.to_csv(output / "predictions.csv", index=False)
    metrics = {"folds": split_rows, "models": {}}
    for model, pred in predictions.groupby("model"):
        ic = rank_ic(pred)
        groups = grouped_returns(pred)
        bt = top_n_backtest(pred, config["model"]["top_n"], config["model"]["holding_days"], config["model"]["cost_bps"])
        bt_stress = top_n_backtest(
            pred,
            config["model"]["top_n"],
            config["model"]["holding_days"],
            config["model"]["stress_cost_bps"],
        )
        ic_std = float(ic.std()) if len(ic) > 1 else 0.0
        yearly_ic = [
            {
                "year": int(year),
                "mean_rank_ic": float(values.mean()),
                "positive_ic_ratio": float((values > 0).mean()),
                "observations": int(len(values)),
            }
            for year, values in ic.groupby(ic.index.year)
        ]
        model_metrics = {
            "mean_rank_ic": float(ic.mean()) if not ic.empty else 0.0,
            "rank_ic_ir": float(ic.mean() / ic_std) if ic_std else 0.0,
            "positive_ic_ratio": float((ic > 0).mean()) if not ic.empty else 0.0,
            "ic_observations": int(len(ic)),
            "yearly_ic": yearly_ic,
            "group_mean_returns": {
                str(int(k)): float(v) for k, v in groups.groupby("group")["fwd_return"].mean().items()
            }
            if not groups.empty
            else {},
            "backtest": summarize_backtest(bt),
            "yearly_backtest": yearly_backtest_summary(bt),
            "stress_backtest": summarize_backtest(bt_stress),
        }
        ic.rename("rank_ic").to_csv(output / f"rank_ic_{model}.csv", header=True)
        groups.to_csv(output / f"grouped_returns_{model}.csv", index=False)
        bt.assign(model=model).to_csv(output / f"backtest_{model}.csv", index=False)
        metrics["models"][model] = model_metrics

    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_manifest(output, config, sample)
    lines = [
        "# 教学研究摘要",
        "",
        f"样本外滚动折数：{len(split_rows)}",
        "",
        "| 模型 | Mean RankIC | 正 IC 比例 | 主动 Sharpe | 最大回撤 | 成本后总收益 | 延迟退出比例 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, result in metrics["models"].items():
        backtest = result["backtest"]
        lines.append(
            f"| {model} | {result['mean_rank_ic']:.4f} | {result['positive_ic_ratio']:.1%} | "
            f"{backtest.get('active_sharpe', 0):.2f} | {backtest.get('max_drawdown', 0):.2%} | "
            f"{backtest.get('total_return', 0):.2%} | {backtest.get('delayed_exit_rate', 0):.1%} |"
        )
    lines += [
        "",
        "验证集用于每折选参；测试集只生成一次样本外预测。股票池按逐日历史流动性选择。",
        "回测在 T+1 检查买入资格，计划退出受阻时顺延到首个可卖日。",
        "以上结果仅用于验证研究代码，不代表真实市场收益。",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return metrics
