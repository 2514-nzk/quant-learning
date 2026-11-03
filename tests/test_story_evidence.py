"""核对第 14 章新增的置换、bootstrap 与 oracle 数字。"""

import math

from examples.story_evidence import evidence_report, load_rows, mean_rank_ic, oracle_score, portfolio_final_money


def test_evidence_report_matches_chapter_numbers():
    report = evidence_report(permutations=500, bootstrap=500, seed=42)

    assert math.isclose(report["test_momentum_mean_rank_ic"], 0.4857142857142857)
    assert 0 < report["permutation_p_value"] <= 0.01
    lower, upper = report["bootstrap_90_interval"]
    assert lower < report["test_momentum_mean_rank_ic"] < upper
    assert math.isclose(report["oracle_test_final_money"], 10442.9779, rel_tol=1e-4)
    assert math.isclose(report["momentum_test_final_money"], 10793.0463, rel_tol=1e-4)


def test_single_factor_rank_ic_does_not_use_future_answers():
    rows = [row for row in load_rows() if row["round_id"] == 1]
    before = mean_rank_ic(rows, lambda row: row["mom_5"])
    changed = [{**row, "fwd_return": -row["fwd_return"]} for row in rows]
    after = mean_rank_ic(changed, lambda row: row["mom_5"])
    assert before == -after  # 只改未来答案，排序相关系数取反，选股输入没有改变。


def test_oracle_portfolio_uses_same_fee_and_top_two():
    rows = [row for row in load_rows() if row["round_id"] == 1]
    assert oracle_score(rows[0]) == 0.12 * rows[0]["mom_5"] + 0.12 * rows[0]["ep"] + 0.08 * rows[0]["roe"]
    assert math.isclose(portfolio_final_money(rows, oracle_score), 8000 * 1.04 * 0.999 / 1.001)
