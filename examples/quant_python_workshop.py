"""量化 Python 教学：面板、市场日历、未来标签、PIT 连接与边界核对。

从项目根目录运行 python examples/quant_python_workshop.py。
仅使用内置虚构行情；不访问数据库，不写文件，不构成策略回测。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_market_data() -> tuple[pd.DatetimeIndex, pd.DataFrame]:
    # 显式教学日历；真实研究应从交易所日历取数，不能用工作日代替。
    calendar = pd.DatetimeIndex(pd.to_datetime([
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
        "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11",
        "2024-01-12", "2024-01-15", "2024-01-16", "2024-01-17",
        "2024-01-18", "2024-01-19", "2024-01-22", "2024-01-23",
        "2024-01-24", "2024-01-25", "2024-01-26", "2024-01-29",
        "2024-01-30", "2024-01-31",
    ]))
    rows = []
    for i, date in enumerate(calendar):
        prices = {
            "A": 10 * 1.01**i,
            "B": 20 * 0.995**i,
            "C": 8 * (1 + 0.004 * i + 0.015 * np.sin(i)),
        }
        for code, close in prices.items():
            if code == "B" and i in (7, 14):
                continue  # 人为设置缺行，不能据此断言真实缺失原因是停牌。
            rows.append({
                "trade_date": date, "code": code,
                "open": close / 1.002, "close": close,
                "amount": 20_000_000 + 100_000 * i,
            })
    return calendar, pd.DataFrame(rows).sample(frac=1, random_state=7).reset_index(drop=True)


def build_panel(raw: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """先统一到市场日历，再按证券生成特征；返回的缺行不被填成零。"""
    if calendar.has_duplicates or not calendar.is_monotonic_increasing:
        raise ValueError("市场日历必须唯一且升序")
    if raw.duplicated(["trade_date", "code"]).any():
        raise ValueError("行情主键重复，请先解释数据来源或修订关系")
    if not raw["trade_date"].isin(calendar).all():
        raise ValueError("行情日期不在市场日历中")
    if not np.isfinite(raw[["open", "close"]].to_numpy()).all():
        raise ValueError("原始价格必须有限；缺行在后续日历对齐时显式生成")
    if (raw[["open", "close"]] <= 0).any().any():
        raise ValueError("价格必须为正")

    index = pd.MultiIndex.from_product(
        [sorted(raw["code"].unique()), calendar], names=["code", "trade_date"]
    )
    grid = raw.set_index(["code", "trade_date"]).reindex(index).reset_index()
    grid["observed"] = grid["close"].notna()
    grouped = grid.groupby("code", sort=False)["close"]
    grid["ret_1d"] = grouped.pct_change(fill_method=None)
    grid["mom_3"] = grouped.pct_change(3, fill_method=None)
    grid["mom_20"] = grouped.pct_change(20, fill_method=None)
    grid["vol_5"] = grid.groupby("code", sort=False)["ret_1d"].transform(
        lambda s: s.rolling(5, min_periods=5).std(ddof=1)
    )
    # 教学资格只检查当前观测与因子；实际研究还需历史 ST/上市/流动性规则。
    grid["signal_eligible"] = grid["observed"] & grid["mom_3"].notna()
    score = grid["mom_3"].where(grid["signal_eligible"])
    grid["rank_pct"] = score.groupby(grid["trade_date"]).rank(method="average", pct=True)
    return grid


def attach_labels(
    panel: pd.DataFrame, raw: pd.DataFrame, calendar: pd.DatetimeIndex, horizon: int = 5,
) -> pd.DataFrame:
    """只构造事后评价标签；这些字段不能进入 T 日选股逻辑。"""
    if horizon < 1:
        raise ValueError("horizon 必须大于等于 1")
    dates = pd.Series(calendar, index=calendar)
    result = panel.copy()
    result["entry_date"] = result["trade_date"].map(dates.shift(-1))
    result["scheduled_exit_date"] = result["trade_date"].map(dates.shift(-horizon))
    entry = raw[["code", "trade_date", "open"]].rename(
        columns={"trade_date": "entry_date", "open": "entry_price"}
    )
    exit_prices = raw[["code", "trade_date", "close"]].rename(
        columns={"trade_date": "scheduled_exit_date", "close": "scheduled_exit_price"}
    )
    result = result.merge(entry, on=["code", "entry_date"], how="left", validate="many_to_one")
    result = result.merge(
        exit_prices, on=["code", "scheduled_exit_date"], how="left", validate="many_to_one"
    )
    result["fwd_return"] = result["scheduled_exit_price"] / result["entry_price"] - 1
    return result.sort_values(["code", "trade_date"]).reset_index(drop=True)


def point_in_time_example() -> pd.DataFrame:
    # 时间均为本地上海时间的教学约定，未混用其他时区。
    decisions = pd.DataFrame({
        "code": ["A", "B", "A", "B", "A", "A"],
        "decision_at": pd.to_datetime([
            "2024-01-04 16:00", "2024-01-04 16:00",
            "2024-01-05 16:00", "2024-01-05 16:00",
            "2024-01-10 16:00", "2024-01-11 16:00",
        ]),
    })
    # 每行是“该时点最新可用的同一指标状态”；最后一行是一次后续修订。
    events = pd.DataFrame({
        "code": ["A", "B", "A"],
        "available_at": pd.to_datetime([
            "2024-01-04 20:00", "2024-01-03 15:00", "2024-01-10 20:00",
        ]),
        "ep": [0.04, 0.06, 0.08],
        "version": ["initial_A", "initial_B", "revised_A"],
    })
    # merge_asof 要求连接的时间键整体递增，不能只按 code 后按时间排序。
    return pd.merge_asof(
        decisions.sort_values(["decision_at", "code"]),
        events.sort_values(["available_at", "code"]),
        left_on="decision_at", right_on="available_at", by="code",
        direction="backward", allow_exact_matches=True,
        tolerance=pd.Timedelta(days=30),
    )


def evaluate_daily(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, day in sample.groupby("trade_date", sort=True):
        signal = day[day["signal_eligible"]]
        pairs = signal.dropna(subset=["mom_3", "fwd_return"])
        rank_ic = np.nan
        if len(pairs) >= 3 and pairs["mom_3"].nunique() > 1 and pairs["fwd_return"].nunique() > 1:
            rank_ic = pairs["mom_3"].rank().corr(pairs["fwd_return"].rank())
        rows.append({
            "trade_date": date, "n_signal": len(signal), "n_evaluable": len(pairs),
            "label_coverage": len(pairs) / len(signal) if len(signal) else np.nan,
            "rank_ic": rank_ic,
        })
    return pd.DataFrame(rows)


def verify_workshop(
    raw: pd.DataFrame, calendar: pd.DatetimeIndex, sample: pd.DataFrame, pit: pd.DataFrame,
) -> None:
    """核对窗口、缺行、并列、公告修订、重复键与前视错误。"""
    assert len(sample) == len(calendar) * raw["code"].nunique()
    assert not sample.duplicated(["code", "trade_date"]).any()
    a = sample[sample["code"].eq("A")].set_index("trade_date")
    assert a["mom_3"].iloc[:3].isna().all()
    assert np.isclose(a["mom_3"].iloc[3], 1.01**3 - 1)
    assert np.isclose(a["mom_20"].iloc[20], 1.01**20 - 1)
    b = sample[sample["code"].eq("B")].set_index("trade_date")
    assert pd.isna(b.loc[calendar[7], "close"])
    assert pd.isna(b.loc[calendar[8], "ret_1d"])
    assert b.loc[calendar[6], "scheduled_exit_date"] == calendar[11]
    assert pd.isna(b.loc[calendar[6], "fwd_return"])  # T+1 缺少买入价
    naive_b = raw[raw["code"].eq("B")].sort_values("trade_date").set_index("trade_date")
    naive_exit = naive_b.index.to_series().shift(-5).loc[calendar[6]]
    assert naive_exit == calendar[12]  # 稀疏表 shift(-5) 错落到后一个交易日
    assert sample[sample["trade_date"].eq(calendar[-1])]["fwd_return"].isna().all()
    assert np.allclose(pd.Series([10., 20., 20., np.nan]).rank(pct=True).dropna(), [1/3, 5/6, 5/6])

    a_pit = pit[pit["code"].eq("A")].sort_values("decision_at")
    assert pd.isna(a_pit["ep"].iloc[0])
    assert np.allclose(a_pit["ep"].iloc[1:], [0.04, 0.04, 0.08])
    known = pit.dropna(subset=["available_at"])
    assert known["available_at"].le(known["decision_at"]).all()

    try:
        build_panel(pd.concat([raw, raw.iloc[[0]]], ignore_index=True), calendar)
    except ValueError as error:
        assert "主键重复" in str(error)
    else:
        raise AssertionError("重复键应被拒绝")

    # 修改最后一天，过去特征必须不变；未来收益标签则允许变化。
    changed = raw.copy()
    changed.loc[changed["trade_date"].eq(calendar[-1]), "close"] *= 100
    original_features = build_panel(raw, calendar)
    changed_features = build_panel(changed, calendar)
    past = original_features["trade_date"].lt(calendar[-1])
    feature_columns = ["ret_1d", "mom_3", "mom_20", "vol_5", "rank_pct"]
    pd.testing.assert_frame_equal(
        original_features.loc[past, feature_columns], changed_features.loc[past, feature_columns]
    )


def main() -> None:
    calendar, raw = make_market_data()
    panel = build_panel(raw, calendar)
    sample = attach_labels(panel, raw, calendar)
    pit = point_in_time_example()
    verify_workshop(raw, calendar, sample, pit)

    date = calendar[6]
    print("虚构数据：仅演示数据处理，三只股票不足以推断因子有效性。")
    print(f"原始行数={len(raw)}，日历网格行数={len(panel)}")
    print("\n2024-01-10 的事后核对表：")
    columns = ["code", "mom_3", "rank_pct", "entry_date", "scheduled_exit_date", "fwd_return"]
    print(sample.loc[sample["trade_date"].eq(date), columns].to_string(index=False))
    # 选股只读 T 时点字段，不按未来收益或买入价是否存在过滤。
    candidates = panel[panel["trade_date"].eq(date) & panel["signal_eligible"]]
    target = candidates.sort_values(["mom_3", "code"], ascending=[False, True]).head(2)
    print("\nT 日目标候选（尚未模拟成交）：", target["code"].tolist())
    print("\n公告与修订的 PIT 连接：")
    print(pit.to_string(index=False))
    print("\n评价覆盖（节选）：")
    print(evaluate_daily(sample).iloc[5:10].to_string(index=False))
    print("\n边界核对全部通过。")


if __name__ == "__main__":
    main()
