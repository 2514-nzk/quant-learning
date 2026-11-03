"""量化 Python 教学：面板、市场日历、未来标签、PIT 连接与边界核对。

从项目根目录运行 python examples/quant_python_workshop.py。
仅使用内置虚构行情；不访问数据库，不写文件，不构成策略回测。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# 这个函数返回两样东西：市场日历和原始行情表；箭头后是类型提示。
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
    rows = []  # 用一个空列表，逐条收集生成的行情记录。
    # enumerate 同时给出从 0 开始的位置 i 和对应日期 date。
    for i, date in enumerate(calendar):
        prices = {
            "A": 10 * 1.01**i,
            "B": 20 * 0.995**i,
            "C": 8 * (1 + 0.004 * i + 0.015 * np.sin(i)),
        }
        # items 每次给出字典里的一对内容：股票名字和它的价格。
        for code, close in prices.items():
            if code == "B" and i in (7, 14):
                continue  # 人为设置缺行，不能据此断言真实缺失原因是停牌。
            # 每次追加一条行情，最后再把所有记录组成 DataFrame 表格。
            rows.append({
                "trade_date": date, "code": code,
                "open": close / 1.002, "close": close,
                "amount": 20_000_000 + 100_000 * i,
            })
    # 把行情行顺序故意打乱，方便观察后面的排序是否正确。
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

    # 把每只股票与每个市场日期配对，列出应有的全部组合。
    index = pd.MultiIndex.from_product(
        [sorted(raw["code"].unique()), calendar], names=["code", "trade_date"]
    )
    # 先用股票加日期定位记录，再按完整网格补齐；缺价仍为 NaN。
    grid = raw.set_index(["code", "trade_date"]).reindex(index).reset_index()
    grid["observed"] = grid["close"].notna()  # notna 表示这行确实有价格，新增布尔列保存这个事实。
    grouped = grid.groupby("code", sort=False)["close"]  # 按股票分组以后，各自计算自己的历史涨幅。
    grid["ret_1d"] = grouped.pct_change(fill_method=None)
    grid["mom_3"] = grouped.pct_change(3, fill_method=None)
    grid["mom_20"] = grouped.pct_change(20, fill_method=None)
    # transform 把每组的五行滚动标准差放回原来的行。
    grid["vol_5"] = grid.groupby("code", sort=False)["ret_1d"].transform(
        lambda s: s.rolling(5, min_periods=5).std(ddof=1)
    )
    # 教学资格只检查当前观测与因子；实际研究还需历史 ST/上市/流动性规则。
    grid["signal_eligible"] = grid["observed"] & grid["mom_3"].notna()
    score = grid["mom_3"].where(grid["signal_eligible"])  # where 保留条件为 True 的分数，其他位置变成缺失。
    # 同一天的有效股票一起排名；并列取平均名次。
    grid["rank_pct"] = score.groupby(grid["trade_date"]).rank(method="average", pct=True)
    return grid


def attach_labels(
    panel: pd.DataFrame, raw: pd.DataFrame, calendar: pd.DatetimeIndex, horizon: int = 5,
) -> pd.DataFrame:
    """只构造事后评价标签；这些字段不能进入 T 日选股逻辑。"""
    if horizon < 1:
        raise ValueError("horizon 必须大于等于 1")
    dates = pd.Series(calendar, index=calendar)  # 用日期同时作为查找键和内容，便于按信号日查未来目标日。
    result = panel.copy()  # 复制表格，新增标签字段时保留原 panel。
    # map 按日期查表；shift(-1) 将下一个市场日作为查找结果。
    result["entry_date"] = result["trade_date"].map(dates.shift(-1))
    # 同样查信号日之后第 horizon 个市场交易日。
    result["scheduled_exit_date"] = result["trade_date"].map(dates.shift(-horizon))
    # 只取买入需要的三列，并把日期和价格列改成用途更明确的名字。
    entry = raw[["code", "trade_date", "open"]].rename(
        columns={"trade_date": "entry_date", "open": "entry_price"}
    )
    # 为计划卖出价准备另一张查找表。
    exit_prices = raw[["code", "trade_date", "close"]].rename(
        columns={"trade_date": "scheduled_exit_date", "close": "scheduled_exit_price"}
    )
    # 按股票与买入日连接；many_to_one 要求右表每个键至多一条。
    result = result.merge(entry, on=["code", "entry_date"], how="left", validate="many_to_one")
    result = result.merge(
        exit_prices, on=["code", "scheduled_exit_date"], how="left", validate="many_to_one"
    )
    # 两个目标日期的价格端点都有值时，才得到这段未来收益。
    result["fwd_return"] = result["scheduled_exit_price"] / result["entry_price"] - 1
    return result.sort_values(["code", "trade_date"]).reset_index(drop=True)


def point_in_time_example() -> pd.DataFrame:
    # 时间均为本地上海时间的教学约定，未混用其他时区。
    # 每一行写下某只股票具体在什么时候做决定。
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
        direction="backward", allow_exact_matches=True,  # 只向过去找可用记录；同一时刻的记录也允许匹配。
        tolerance=pd.Timedelta(days=30),  # 超过 30 天还没有更新的旧记录不再匹配，保留缺失。
    )


# 输入整张样本表，输出每个日期的覆盖数量和排序评价。
def evaluate_daily(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    # 每次取出一个日期，以及这个日期对应的小表 day。
    for date, day in sample.groupby("trade_date", sort=True):
        signal = day[day["signal_eligible"]]
        pairs = signal.dropna(subset=["mom_3", "fwd_return"])  # 评价要有成对的因子与未来答案，两者缺一就先排除。
        rank_ic = np.nan  # 先设为缺失；样本太少或全常数时不伪造相关系数。
        if len(pairs) >= 3 and pairs["mom_3"].nunique() > 1 and pairs["fwd_return"].nunique() > 1:
            rank_ic = pairs["mom_3"].rank().corr(pairs["fwd_return"].rank())  # 两列先各自排名，再算名次之间的相关性。
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
    assert len(sample) == len(calendar) * raw["code"].nunique()  # assert 后面的条件不成立就报错；这里核对网格总行数。
    assert not sample.duplicated(["code", "trade_date"]).any()
    a = sample[sample["code"].eq("A")].set_index("trade_date")  # 只抽出 A 的记录，以日期作行标签，逐日检查窗口首值。
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

    a_pit = pit[pit["code"].eq("A")].sort_values("decision_at")  # 再抽出 A 的公告连接记录，按决策时刻检查版本有没有提前出现。
    assert pd.isna(a_pit["ep"].iloc[0])
    assert np.allclose(a_pit["ep"].iloc[1:], [0.04, 0.04, 0.08])
    known = pit.dropna(subset=["available_at"])
    assert known["available_at"].le(known["decision_at"]).all()

    # 故意追加一条重复记录，检查程序是否会拒绝它。
    try:
        build_panel(pd.concat([raw, raw.iloc[[0]]], ignore_index=True), calendar)
    except ValueError as error:
        assert "主键重复" in str(error)
    else:
        raise AssertionError("重复键应被拒绝")

    # 修改最后一天，过去特征必须不变；未来收益标签则允许变化。
    changed = raw.copy()
    changed.loc[changed["trade_date"].eq(calendar[-1]), "close"] *= 100
    original_features = build_panel(raw, calendar)  # 分别重算原数据和修改后的数据，再对比它们的过去特征。
    changed_features = build_panel(changed, calendar)
    past = original_features["trade_date"].lt(calendar[-1])
    feature_columns = ["ret_1d", "mom_3", "mom_20", "vol_5", "rank_pct"]
    # 逐项核对两张表是否相同，不同就报告具体位置。
    pd.testing.assert_frame_equal(
        original_features.loc[past, feature_columns], changed_features.loc[past, feature_columns]
    )


def main() -> None:
    calendar, raw = make_market_data()  # 接收两个返回值：日历和原始行情。
    panel = build_panel(raw, calendar)  # 补齐日历网格，并生成只读过去数据的特征。
    sample = attach_labels(panel, raw, calendar)  # 把未来价格接入评价表；不把它们交给选股条件。
    pit = point_in_time_example()
    verify_workshop(raw, calendar, sample, pit)  # 运行上面写好的核对步骤，有异常会在这里报错。

    date = calendar[6]
    print("虚构数据：仅演示数据处理，三只股票不足以推断因子有效性。")
    print(f"原始行数={len(raw)}，日历网格行数={len(panel)}")
    print("\n2024-01-10 的事后核对表：")
    columns = ["code", "mom_3", "rank_pct", "entry_date", "scheduled_exit_date", "fwd_return"]
    print(sample.loc[sample["trade_date"].eq(date), columns].to_string(index=False))
    # 选股只读 T 时点字段，不按未来收益或买入价是否存在过滤。
    candidates = panel[panel["trade_date"].eq(date) & panel["signal_eligible"]]
    # 动量从高到低，同分按名字排，再取前两只。
    target = candidates.sort_values(["mom_3", "code"], ascending=[False, True]).head(2)
    print("\nT 日目标候选（尚未模拟成交）：", target["code"].tolist())
    print("\n公告与修订的 PIT 连接：")
    print(pit.to_string(index=False))
    print("\n评价覆盖（节选）：")
    print(evaluate_daily(sample).iloc[5:10].to_string(index=False))
    print("\n边界核对全部通过。")


# 直接运行该文件时才调用 main；被其他文件导入时不自动运行。
if __name__ == "__main__":
    main()
