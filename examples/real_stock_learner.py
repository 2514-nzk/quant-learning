#!/usr/bin/env python3
"""Real 2024 four-famous-A-share OHLC arithmetic exercise, no external libraries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "data" / "real_a_share" / "teaching_case.json"


def rank_ic(rows: list[dict]) -> float:
    """Spearman rank correlation for four observations without ties.

    Predictive scores sort descending (1 is highest), actual returns sort descending.
    """
    ids = [x["symbol"] for x in rows]
    pred = {row["symbol"]:i + 1 for i,row in enumerate(sorted(rows,key=lambda r:(-r["mom5"],r["symbol"])))}
    actual = {row["symbol"]:i + 1 for i,row in enumerate(sorted(rows,key=lambda r:(-r["forward_return"],r["symbol"])))}
    # 4-stock Spearman formula applies when both orderings are unique.
    if len({x["forward_return"] for x in rows}) != len(rows):
        raise ValueError("Return ties require average ranks, not this simplified formula")
    return 1 - 6*sum((pred[x]-actual[x])**2 for x in ids)/(4*(4**2-1))


def summarize(rounds: list[dict]) -> dict:
    growth = 1.0
    baseline = 1.0
    ics = []
    for item in rounds:
        growth *= 1 + item["top2_gross"]
        baseline *= 1 + item["all4_gross"]
        ics.append(rank_ic(item["rows"]))
    return {
        "periods":len(rounds),
        "mean_ic":sum(ics)/len(ics),
        "selected_total_pct":(growth-1)*100,
        "baseline_total_pct":(baseline-1)*100,
    }


def run(period: int | None = None) -> None:
    case=json.loads(CASE.read_text(encoding="utf-8"))
    rows=case["rounds"]
    current=rows[-1] if period is None else rows[period-1]
    print("四只真实 A 股，2024 年不复权历史日线（教学，不是收益承诺）")
    print(f"决策：{current['signal_date']}收盘后；尝试买入：{current['entry_date']}开盘；观察到：{current['exit_date']}收盘")
    print("日期       股票            过去5日涨幅  未来观察收益")
    for x in current["rows"]:
        print(f"{x['signal_date']} {x['name']:<6}({x['symbol']})  {x['mom5']*100:+8.2f}%    {x['forward_return']*100:+8.2f}%")
    chosen="、".join(x["name"] for x in current["rows"][:2])
    print(f"按过去5日涨幅选前2名：{chosen}")
    print(f"各分50万元（允许理论份额）未扣费期末：{current['theoretical_end']:,.2f} 元")
    print(f"四只等权同一时间对照：{current['benchmark_end']:,.2f} 元")
    print(f"每次买入按100股整数倍取整的账面期末：{current['lot_end']:,.2f} 元")
    print("这些数字没有计入分红/费用/真实委托成交；不同的成交限制不能用这张表证明。")
    print("\n18个非重叠教学期（不代表完整历史股票池）：")
    for name,sl in (("前10期（学习）",rows[:10]),("中4期（比较）",rows[10:14]),("后4期（演示留出）",rows[14:])):
        s=summarize(sl)
        print(f"{name}: {s['periods']}期，平均RankIC {s['mean_ic']:+.3f}，"
              f"理论选股复利 {s['selected_total_pct']:+.2f}%，四股等权 {s['baseline_total_pct']:+.2f}%")
    print("只有4只知名股票、18期。样本太小，不可将这张成绩单当成实盘策略有效性证据。")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--round",type=int,choices=range(1,19),default=None,metavar="1..18")
    args=parser.parse_args()
    run(args.round)
