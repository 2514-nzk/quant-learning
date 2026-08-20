from pathlib import Path

import duckdb

from src.duckdb_data import load_market_panel


def test_daily_liquidity_universe_does_not_use_future_amount(tmp_path: Path):
    database = tmp_path / "market.duckdb"
    con = duckdb.connect(str(database))
    con.execute(
        "create table stock_basic(ts_code varchar, list_date varchar, delist_date varchar, list_board_name varchar)"
    )
    con.execute("insert into stock_basic values ('A','20200101',null,'主板'), ('B','20200101',null,'主板')")
    con.execute(
        "create table daily(trade_date varchar, ts_code varchar, adj_open double, adj_high double, adj_low double, adj_close double, volume double, amount double, trade_status varchar)"
    )
    con.execute(
        "create table daily_basic(trade_date varchar, ts_code varchar, total_mv double, turnover_rate double, udlimit_status varchar)"
    )
    amounts = {
        "20200102": {"A": 100.0, "B": 50.0},
        "20200103": {"A": 100.0, "B": 50.0},
        "20200106": {"A": 100.0, "B": 1000.0},
    }
    for date, by_code in amounts.items():
        for code, amount in by_code.items():
            con.execute(
                "insert into daily values (?, ?, 10, 11, 9, 10, 100, ?, '交易')",
                [date, code, amount],
            )
            con.execute("insert into daily_basic values (?, ?, 1000, 1, '0')", [date, code])
    con.close()

    panel = load_market_panel(
        database,
        start="20200103",
        end="20200106",
        max_stocks=1,
        min_observations=2,
        liquidity_lookback=2,
    )
    eligible = panel[panel.signal_eligible]
    selected = eligible.set_index(eligible.trade_date.dt.strftime("%Y%m%d"))["code"].to_dict()
    assert selected["20200103"] == "A"
    assert selected["20200106"] == "B"
