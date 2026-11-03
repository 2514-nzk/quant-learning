"""重做正文里的纸面研究。数据全为教学构造，不读取真实行情。

基础演算：python examples/story_research.py
模型比较：python examples/story_research.py --models
保存报告：python examples/story_research.py --models --output outputs/story/report.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "story" / "rounds.csv"
FEATURES = ["mom_5", "ep", "roe"]  # 只取当时已知的三列，未来收益不在这里。
SEED = 42
FEE = 0.001  # 每侧按成交金额收 0.1%；只是本故事统一的教学费率。


def text_sha256(path: Path) -> str:
    # 统一换行后再计算指纹，Windows 与 Linux 的同一份文本得到相同结果。
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def load_rows() -> list[dict]:
    with DATA.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))  # CSV 每行变成一个按列名取值的字典。
    for row in rows:
        for name in ("round_id", "signal_day", "entry_day", "exit_day", "feature_available_day"):
            row[name] = int(row[name])
        for name in (*FEATURES, "fwd_return"):
            row[name] = float(row[name])
        assert row["feature_available_day"] <= row["signal_day"]
        assert row["signal_day"] < row["entry_day"] < row["exit_day"]
        assert all(math.isfinite(row[name]) for name in (*FEATURES, "fwd_return"))
    assert len({(row["round_id"], row["code"]) for row in rows}) == len(rows)
    for number in range(1, 61):
        assert sorted(row["code"] for row in rows if row["round_id"] == number) == list("ABCD")
    return rows


def ranks(values: list[float]) -> list[float]:
    """返回升序平均名次，供四只股票的手算与同分情况核对。"""
    result = []
    for value in values:
        lower = sum(item < value for item in values)
        equal = sum(item == value for item in values)
        result.append(lower + (equal + 1) / 2)
    return result


def rank_ic(scores: list[float], returns: list[float]) -> float | None:
    left, right = ranks(scores), ranks(returns)
    a = [item - mean(left) for item in left]
    b = [item - mean(right) for item in right]
    denominator = math.sqrt(sum(x*x for x in a) * sum(y*y for y in b))
    if denominator == 0:
        return None  # 常数分数没有区分力，相关系数无定义。
    return sum(x*y for x, y in zip(a, b)) / denominator


def factor_scores(rows: list[dict], names: list[str]) -> dict[str, float]:
    scores = {row["code"]: 0.0 for row in rows}
    for name in names:
        positions = ranks([row[name] for row in rows])
        for row, position in zip(rows, positions):
            scores[row["code"]] += position / len(rows) / len(names)
    return scores


def select_two(rows: list[dict], scores: dict[str, float]) -> list[dict]:
    # 分数从高到低；同分时按名字排序，让每次重做得到相同名单。
    return sorted(rows, key=lambda row: (-scores[row["code"]], row["code"]))[:2]


def replay_first_round(blocked: tuple[str, ...] = (), fee: float = 0.0) -> dict:
    """回到第一期的原始 8000 元，独立比较一次买入、卖出与现金。"""
    first = [row for row in load_rows() if row["round_id"] == 1]
    chosen = select_two(first, factor_scores(first, ["mom_5"]))
    entry_prices = {"A": 10.0, "B": 20.0, "C": 8.0, "D": 15.0}
    ledger = []
    final_money = 0.0
    for row in chosen:
        code = row["code"]
        entry = entry_prices[code]
        exit_price = entry * (1 + row["fwd_return"])  # 与同一 CSV 的未来答案保持一致。
        budget = 4000.0
        if code in blocked:
            final_money += budget  # 买不到就保留现金，不临时改成全买另一只。
            ledger.append({"code": code, "status": "cash", "budget": budget, "cash": budget})
            continue
        notional = budget / (1 + fee)  # 这 4000 元同时要够支付买入金额和买入费用。
        buy_fee = notional * fee
        quantity = notional / entry  # 为看清算术，允许虚拟份额，不模拟整手。
        sell_notional = quantity * exit_price
        sell_fee = sell_notional * fee
        cash = sell_notional - sell_fee
        final_money += cash
        ledger.append({"code": code, "status": "filled", "budget": budget,
                       "buy_notional": notional, "buy_fee": buy_fee, "quantity": quantity,
                       "sell_notional": sell_notional, "sell_fee": sell_fee, "cash": cash})
    return {"initial_money": 8000.0, "final_money": final_money,
            "profit": final_money - 8000, "fee_per_side": fee,
            "blocked": list(blocked), "ledger": ledger}


def basic_report(rows: list[dict]) -> dict:
    wealth = benchmark = combined_wealth = 8000.0
    peak = wealth
    records = []
    for number in range(1, 5):
        day = [row for row in rows if row["round_id"] == number]
        mom = factor_scores(day, ["mom_5"])
        combined = factor_scores(day, FEATURES)
        selected = select_two(day, mom)
        combined_selected = select_two(day, combined)
        gross = mean(row["fwd_return"] for row in selected)
        reference = mean(row["fwd_return"] for row in day)
        wealth *= 1 + gross
        benchmark *= 1 + reference
        combined_wealth *= 1 + mean(row["fwd_return"] for row in combined_selected)
        peak = max(peak, wealth)
        records.append({"round": number, "selected": [row["code"] for row in selected],
                        "gross_return": gross, "benchmark_return": reference,
                        "active_return": gross-reference, "wealth": wealth,
                        "benchmark_wealth": benchmark, "drawdown": wealth/peak-1,
                        "rank_ic": rank_ic([mom[row["code"]] for row in day],
                                           [row["fwd_return"] for row in day]),
                        "combined_selected": [row["code"] for row in combined_selected],
                        "combined_wealth": combined_wealth})
    return {"rounds": records, "mean_rank_ic": mean(row["rank_ic"] for row in records),
            "execution": {"ideal": replay_first_round(),
                          "blocked_only": replay_first_round(("C",)),
                          "fee_only": replay_first_round(fee=FEE),
                          "blocked_and_fee": replay_first_round(("C",), FEE)}}


def prediction_metrics(frame, scores) -> dict:
    table = frame.copy()
    table["score"] = list(scores)
    daily_ics, gross_returns = [], []
    wealth = benchmark = 8000.0
    peak = wealth
    maximum_drawdown = 0.0
    for _, day in table.groupby("round_id", sort=True):
        ordered = day.sort_values(["score", "code"], ascending=[False, True])
        gross = float(ordered.head(2)["fwd_return"].mean())
        reference = float(day["fwd_return"].mean())
        ic = rank_ic(day["score"].tolist(), day["fwd_return"].tolist())
        if ic is not None:
            daily_ics.append(ic)
        gross_returns.append(gross)
        # 每期全部买入、到期全部卖出；买入费用也从该期预算中支付。
        wealth *= (1 + gross) * (1 - FEE) / (1 + FEE)
        benchmark *= (1 + reference) * (1 - FEE) / (1 + FEE)
        peak = max(peak, wealth)
        maximum_drawdown = min(maximum_drawdown, wealth / peak - 1)
    return {"mean_rank_ic": mean(daily_ics) if daily_ics else None,
            "positive_ic_ratio": mean(ic > 0 for ic in daily_ics) if daily_ics else None,
            "mean_gross_return": mean(gross_returns), "final_money": wealth,
            "total_net_return": wealth / 8000 - 1, "max_drawdown": maximum_drawdown,
            "benchmark_final_money": benchmark,
            "cumulative_active_difference": (wealth-benchmark)/8000}


def model_report(rows: list[dict]) -> dict:
    import lightgbm as lgb
    import numpy as np
    import pandas as pd
    import sklearn
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    frame = pd.DataFrame(rows)
    frame["label_rank"] = frame.groupby("round_id")["fwd_return"].rank(pct=True)
    train = frame[frame["round_id"] <= 36].copy()
    validation = frame[frame["round_id"].between(37, 46)].copy()
    test = frame[frame["round_id"] >= 47].copy()
    assert train["exit_day"].max() < validation["signal_day"].min()
    assert validation["exit_day"].max() < test["signal_day"].min()
    trials = []

    def evaluate_candidate(family, parameter, model):
        model.fit(train[FEATURES], train["label_rank"])
        a = prediction_metrics(train, model.predict(train[FEATURES]))
        b = prediction_metrics(validation, model.predict(validation[FEATURES]))
        trials.append({"family": family, "parameter": parameter,
                       "train_rank_ic": a["mean_rank_ic"], "validation_rank_ic": b["mean_rank_ic"]})
        return b["mean_rank_ic"]

    ridge_results = []
    for alpha in (0.1, 1.0, 10.0):
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        score = evaluate_candidate("Ridge", {"alpha": alpha}, model)
        ridge_results.append((score, alpha))
    best_alpha = max(ridge_results, key=lambda item: item[0])[1]

    forest_results = []
    for depth in (2, 4, None):
        model = RandomForestRegressor(n_estimators=100, max_depth=depth,
                                      min_samples_leaf=1, random_state=SEED, n_jobs=1)
        score = evaluate_candidate("RandomForest", {"max_depth": depth}, model)
        forest_results.append((score, depth))
    best_depth = max(forest_results, key=lambda item: item[0])[1]

    boost_settings = dict(num_leaves=7, max_depth=3, min_child_samples=8,
                          learning_rate=0.05, random_state=SEED, n_jobs=1,
                          verbosity=-1, deterministic=True, force_col_wise=True)
    for trees in (15, 50, 150):
        evaluate_candidate("LightGBM", {"n_estimators": trees},
                           lgb.LGBMRegressor(n_estimators=trees, **boost_settings))
    early = lgb.LGBMRegressor(n_estimators=200, **boost_settings)
    early.fit(train[FEATURES], train["label_rank"],
              eval_set=[(validation[FEATURES], validation["label_rank"])],
              callbacks=[lgb.early_stopping(20, verbose=False)])
    best_iteration = int(early.best_iteration_)

    train_validation = frame[frame["round_id"] <= 46]
    models = {
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=best_alpha)),
        "RandomForest": RandomForestRegressor(n_estimators=100, max_depth=best_depth,
                                               min_samples_leaf=1, random_state=SEED, n_jobs=1),
        "LightGBM": lgb.LGBMRegressor(n_estimators=best_iteration, **boost_settings),
    }
    test_results = {}
    test_results["momentum"] = prediction_metrics(test, test["mom_5"])
    ranked = test.groupby("round_id")[FEATURES].rank(pct=True).mean(axis=1)
    test_results["equal_rank"] = prediction_metrics(test, ranked)
    for name, model in models.items():
        model.fit(train_validation[FEATURES], train_validation["label_rank"])
        test_results[name] = prediction_metrics(test, model.predict(test[FEATURES]))

    ablations = {}
    for omitted in FEATURES:
        kept = [name for name in FEATURES if name != omitted]
        model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
        model.fit(train[kept], train["label_rank"])
        ablations[omitted] = prediction_metrics(validation, model.predict(validation[kept]))["mean_rank_ic"]
    return {"versions": {"python": platform.python_version(), "numpy": np.__version__,
                         "pandas": pd.__version__, "sklearn": sklearn.__version__, "lightgbm": lgb.__version__},
            "split": {"train": [1, 36], "validation": [37, 46], "test": [47, 60]},
            "features": FEATURES, "seed": SEED, "fee_per_side": FEE,
            "execution_assumption": "fractional positions; all orders fill; full liquidation each round; no real A-share execution",
            "trials": trials, "chosen": {"ridge_alpha": best_alpha, "forest_depth": best_depth,
                                           "lightgbm_iteration_by_validation_l2": best_iteration},
            "ridge_standardized_weights": {
                name: float(value) for name, value in
                zip(FEATURES, models["Ridge"].named_steps["ridge"].coef_)
            },
            "ridge_intercept": float(models["Ridge"].named_steps["ridge"].intercept_),
            "validation_ablation_omit": ablations, "test": test_results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", action="store_true", help="另运行需要 sklearn 与 LightGBM 的模型练习")
    parser.add_argument("--output", type=Path, help="把本次报告保存为 JSON 文件")
    args = parser.parse_args()
    rows = load_rows()
    report = {"data_kind": "hand-constructed teaching snapshots; not market data",
              "fixture_sha256": text_sha256(DATA),
              "history_sha256": text_sha256(DATA.parent / "price_history.csv"),
              "script_sha256": text_sha256(Path(__file__)),
              "basic": basic_report(rows)}
    for row in report["basic"]["rounds"]:
        print(f"R{row['round']:02d} 选{','.join(row['selected'])} 组合{row['gross_return']:.2%} "
              f"基准{row['benchmark_return']:.2%} 资金{row['wealth']:.2f} RankIC={row['rank_ic']:.2f}")
    for name, replay in report["basic"]["execution"].items():
        print(f"第一期重放 {name}: {replay['final_money']:.2f} 元")
    if args.models:
        report["models"] = model_report(rows)
        print(json.dumps(report["models"], ensure_ascii=False, indent=2, allow_nan=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(f"报告已保存：{args.output}")


if __name__ == "__main__":
    main()
