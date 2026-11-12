#!/usr/bin/env python3
"""Recalculate real 2023 CATL annual-report accounting figures for beginners.

Reads a frozen, cited transcription of CATL's published *consolidated* report;
does not fetch live figures or infer whether any firm committed fraud.
No external Python packages required.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "financial_reports" / "catl_2023_annual_excerpt.json"


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def calculate(data: dict) -> dict[str, float]:
    past, current = data["years"]["2022"], data["years"]["2023"]
    result = {
        "total_equity_100m": current["total_equity"] / 10000,
        "parent_equity_100m": current["parent_equity"] / 10000,
        "minority_equity_100m": current["minority_equity"] / 10000,
        "consolidated_profit_100m": current["consolidated_net_profit"] / 10000,
        "parent_profit_100m": current["parent_net_profit"] / 10000,
        "minority_profit_100m": current["minority_profit"] / 10000,
        "cfo_to_consolidated_profit": current["operating_cash_flow"] / current["consolidated_net_profit"],
        "receivables_growth_pct": (current["accounts_receivable_net"] / past["accounts_receivable_net"] - 1) * 100,
        "inventory_growth_pct": (current["inventory_net"] / past["inventory_net"] - 1) * 100,
        "revenue_growth_pct": (current["revenue"] / past["revenue"] - 1) * 100,
        "minority_equity_percent": current["minority_equity"] / current["total_equity"] * 100,
        "inventory_allowance_100m": current["inventory_allowance"] / 10000,
    }
    # Published tables round individual line items to 0.01 ten-thousand CNY;
    # allow a tiny last-digit difference, not a balance sheet mismatch.
    if abs(current["parent_equity"] + current["minority_equity"] - current["total_equity"]) > 0.03:
        raise ValueError("合并权益与归母及少数股东权益不相符")
    if abs(current["parent_net_profit"] + current["minority_profit"] - current["consolidated_net_profit"]) > 0.03:
        raise ValueError("合并净利润与归母及少数股东损益不相符")
    if abs(current["inventory_gross"] - current["inventory_allowance"] - current["inventory_net"]) > 0.03:
        raise ValueError("存货账面余额、减值准备与账面价值不相符")
    return result


def report(data: dict, result: dict[str, float]) -> str:
    return "\n".join([
        "宁德时代 2023 年年度报告｜真实合并财务报表手算练习",
        "以下为年报已披露的历史数据，不是今天的实时财务信息。",
        f"年末合并权益：{result['total_equity_100m']:,.2f} 亿元",
        f"  其中归母权益：{result['parent_equity_100m']:,.2f} 亿元",
        f"  其中少数股东权益：{result['minority_equity_100m']:,.2f} 亿元",
        f"合并净利润：{result['consolidated_profit_100m']:,.2f} 亿元",
        f"  归母净利润：{result['parent_profit_100m']:,.2f} 亿元",
        f"  少数股东损益：{result['minority_profit_100m']:,.2f} 亿元",
        f"经营现金流／合并净利润：{result['cfo_to_consolidated_profit']:.2f} 倍",
        f"应收账款账面价值同比：{result['receivables_growth_pct']:+.2f}%",
        f"存货账面价值同比：{result['inventory_growth_pct']:+.2f}%",
        f"营业收入同比：{result['revenue_growth_pct']:+.2f}%",
        f"年报披露的加权平均ROE：{data['years']['2023']['reported_weighted_average_roe_percent']:.2f}%",
        "这些数字仅用于财报结构、口径和风险线索学习，不构成舞弊认定或投资建议。",
        f"年报来源：{data['document_url']}",
    ])


def main() -> None:
    data = load()
    print(report(data, calculate(data)))


if __name__ == "__main__":
    main()
