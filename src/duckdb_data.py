"""只读加载本地 Tushare DuckDB，并转换为课程统一样本格式。"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from .dataset import build_features_and_labels


def resolve_snapshot(pointer_path: str | Path) -> Path:
    pointer = Path(pointer_path)
    data = json.loads(pointer.read_text(encoding="utf-8"))
    snapshot = Path(data["snapshot_database"])
    if not snapshot.exists():
        raise FileNotFoundError(f"DuckDB snapshot not found: {snapshot}")
    return snapshot


def inspect_database(database_path: str | Path) -> dict:
    con = duckdb.connect(str(database_path), read_only=True)
    try:
        return {
            "daily": con.sql("select min(trade_date), max(trade_date), count(*), count(distinct ts_code) from daily").fetchone(),
            "daily_basic": con.sql("select min(trade_date), max(trade_date), count(*), count(distinct ts_code) from daily_basic").fetchone(),
            "sector_snapshot": con.sql("select min(trade_date), max(trade_date), count(distinct trade_date) from qmt_sector_member_snapshot").fetchone(),
        }
    finally:
        con.close()


def load_market_panel(
    database_path: str | Path,
    start: str,
    end: str,
    max_stocks: int = 60,
    min_observations: int = 60,
    liquidity_lookback: int = 60,
) -> pd.DataFrame:
    """逐日仅用当时历史成交额选择股票，避免全区间选股前视。"""
    if max_stocks <= 0 or min_observations <= 0 or liquidity_lookback <= 0:
        raise ValueError("max_stocks, min_observations and liquidity_lookback must be positive")
    window_rows = liquidity_lookback - 1
    con = duckdb.connect(str(database_path), read_only=True)
    sql = f"""
        with base as (
            select
                d.trade_date,
                d.ts_code,
                d.adj_open,
                d.adj_high,
                d.adj_low,
                d.adj_close,
                d.volume,
                d.amount,
                d.trade_status,
                b.total_mv,
                b.turnover_rate,
                b.udlimit_status,
                s.list_date,
                s.delist_date,
                s.list_board_name
            from daily d
            join daily_basic b on d.ts_code = b.ts_code and d.trade_date = b.trade_date
            join stock_basic s on d.ts_code = s.ts_code
            where d.trade_date <= ?
              and s.list_board_name in ('主板', '创业板', '科创板')
              and coalesce(s.list_date, '99999999') <= d.trade_date
              and (s.delist_date is null or s.delist_date = '' or s.delist_date >= d.trade_date)
        ), history as (
            select
                *,
                avg(amount) over (
                    partition by ts_code order by trade_date
                    rows between {window_rows} preceding and current row
                ) as trailing_avg_amount,
                count(amount) over (
                    partition by ts_code order by trade_date
                    rows between {window_rows} preceding and current row
                ) as trailing_observations
            from base
        ), ranked as (
            select
                *,
                row_number() over (
                    partition by trade_date
                    order by trailing_avg_amount desc nulls last, ts_code
                ) as universe_rank
            from history
            where trailing_observations >= ? and trade_status <> '停牌'
        ), selected_codes as (
            select distinct ts_code
            from ranked
            where trade_date between ? and ? and universe_rank <= ?
        )
        select
            h.trade_date,
            h.ts_code as code,
            h.adj_open as open,
            h.adj_high as high,
            h.adj_low as low,
            h.adj_close as close,
            h.volume,
            h.amount,
            h.total_mv as market_cap,
            h.turnover_rate,
            h.trade_status,
            h.udlimit_status,
            h.list_date,
            h.delist_date,
            h.list_board_name,
            h.trailing_avg_amount,
            h.trailing_observations,
            r.universe_rank
        from history h
        join selected_codes s on h.ts_code = s.ts_code
        left join ranked r on h.ts_code = r.ts_code and h.trade_date = r.trade_date
        where h.trade_date between ? and ?
        order by h.trade_date, h.ts_code
    """
    try:
        panel = con.execute(
            sql,
            [end, min_observations, start, end, max_stocks, start, end],
        ).fetchdf()
    finally:
        con.close()
    panel["trade_date"] = pd.to_datetime(panel["trade_date"], format="%Y%m%d")
    status = panel["udlimit_status"].fillna("0").astype(str).str.strip().str.lower()
    tradeable = panel["trade_status"].ne("停牌")
    upper = status.isin({"1", "1.0", "u", "up", "涨停"})
    lower = status.isin({"-1", "-1.0", "d", "down", "跌停"})
    panel["is_tradeable"] = tradeable
    panel["signal_eligible"] = tradeable & panel["universe_rank"].le(max_stocks)
    panel["can_buy"] = tradeable & ~upper
    panel["can_sell"] = tradeable & ~lower
    panel["sector"] = "UNKNOWN"  # 历史行业快照不足，禁止用当前分类回填。
    return panel


def build_real_features_and_labels(
    panel: pd.DataFrame, horizon: int = 5, min_history: int = 1
) -> pd.DataFrame:
    return build_features_and_labels(panel, horizon, min_history)
