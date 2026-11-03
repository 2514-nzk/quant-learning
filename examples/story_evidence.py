"""复算第 14 章的证据强度：置换检验、自助区间与 oracle 对照。

运行：python examples/story_evidence.py
数据：data/story/rounds.csv；全部为教学构造，不是真实行情。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "story" / "rounds.csv"
FEATURES = ("mom_5", "ep", "roe")  # 三列当时已知的输入；未来收益不在这里。
SEED = 42
FEE = 0.001  # 与正文一致：每侧成交金额的 0.1%。


def load_rows() -> list[dict]:
    with DATA.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for name in ("round_id", "signal_day", "entry_day", "exit_day", "feature_available_day"):
            row[name] = int(row[name])
        for name in (*FEATURES, "fwd_return"):
            row[name] = float(row[name])
    return rows


def ranks(values: list[float]) -> list[float]:
    # 升序平均名次；并列时共享名次，和正文的手算口径一致。
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
    denominator = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    if denominator == 0:
        return None  # 常数分数没有区分力，相关系数无定义。
    return sum(x * y for x, y in zip(a, b)) / denominator


def by_round(rows: list[dict]) -> list[list[dict]]:
    groups: dict[int, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["round_id"], []).append(row)
    return [groups[key] for key in sorted(groups)]


def mean_rank_ic(rows: list[dict], score) -> float:
    values = []
    for group in by_round(rows):
        ic = rank_ic([score(row) for row in group], [row["fwd_return"] for row in group])
        if ic is not None:
            values.append(ic)
    return mean(values)


def oracle_score(row: dict) -> float:
    # data/story/README.md 记录的生成式；共同扰动在同一期相同，不影响横截面排名。
    return 0.12 * row["mom_5"] + 0.12 * row["ep"] + 0.08 * row["roe"]


def permutation_p_value(rows: list[dict], score, observed: float, repeats: int, rng: random.Random) -> float:
    """每期内部打乱分数，模拟“分数没有横截面信息”的原假设。"""
    groups = by_round(rows)
    count = 0
    for _ in range(repeats):
        values = []
        for group in groups:
            shuffled = [score(row) for row in group]
            rng.shuffle(shuffled)  # 只在同一期的四只股票之间交换分数。
            ic = rank_ic(shuffled, [row["fwd_return"] for row in group])
            if ic is not None:
                values.append(ic)
        if mean(values) >= observed:
            count += 1
    return (count + 1) / (repeats + 1)


def bootstrap_interval(rows: list[dict], score, repeats: int, rng: random.Random) -> tuple[float, float]:
    """对 14 期做有放回重抽，得到 mean RankIC 的教学近似区间。"""
    ics = []
    for group in by_round(rows):
        ic = rank_ic([score(row) for row in group], [row["fwd_return"] for row in group])
        if ic is not None:
            ics.append(ic)
    samples = []
    for _ in range(repeats):
        sample = [rng.choice(ics) for _ in ics]
        samples.append(mean(sample))
    samples.sort()
    return samples[int(0.05 * (repeats - 1))], samples[int(0.95 * (repeats - 1))]


def portfolio_final_money(rows: list[dict], score, fee: float = FEE) -> float:
    """按正文的 Top-2、每期全卖、买卖各收费假设重放测试段。"""
    wealth = 8000.0
    for group in by_round(rows):
        selected = sorted(group, key=lambda row: (-score(row), row["code"]))[:2]
        gross = mean(row["fwd_return"] for row in selected)
        wealth *= (1 + gross) * (1 - fee) / (1 + fee)
    return wealth


def evidence_report(permutations: int = 5000, bootstrap: int = 5000, seed: int = SEED) -> dict:
    rows = load_rows()
    splits = {
        "train": [row for row in rows if row["round_id"] <= 36],
        "validation": [row for row in rows if 37 <= row["round_id"] <= 46],
        "test": [row for row in rows if row["round_id"] >= 47],
    }
    factor_ic = {
        name: {split: mean_rank_ic(part, lambda row, name=name: row[name]) for split, part in splits.items()}
        for name in FEATURES
    }
    oracle_ic = {split: mean_rank_ic(part, oracle_score) for split, part in splits.items()}
    test = splits["test"]
    observed = mean_rank_ic(test, lambda row: row["mom_5"])
    rng = random.Random(seed)
    p_value = permutation_p_value(test, lambda row: row["mom_5"], observed, permutations, rng)
    lower, upper = bootstrap_interval(test, lambda row: row["mom_5"], bootstrap, rng)
    return {
        "factor_mean_rank_ic": factor_ic,
        "oracle_mean_rank_ic": oracle_ic,
        "test_momentum_mean_rank_ic": observed,
        "permutation_p_value": p_value,
        "bootstrap_90_interval": [lower, upper],
        "oracle_test_final_money": portfolio_final_money(test, oracle_score),
        "momentum_test_final_money": portfolio_final_money(test, lambda row: row["mom_5"]),
    }


def format_report(report: dict) -> str:
    lines = ["单因子 mean RankIC（训练 / 验证 / 测试）"]
    for name, values in report["factor_mean_rank_ic"].items():
        lines.append(f"  {name:6s} {values['train']:.3f} / {values['validation']:.3f} / {values['test']:.3f}")
    oracle = report["oracle_mean_rank_ic"]
    lines.append(f"  oracle {oracle['train']:.3f} / {oracle['validation']:.3f} / {oracle['test']:.3f}")
    lines.append("")
    lines.append(f"测试动量 mean RankIC：{report['test_momentum_mean_rank_ic']:.4f}")
    lines.append(f"置换检验 p 值：{report['permutation_p_value']:.4f}")
    lower, upper = report["bootstrap_90_interval"]
    lines.append(f"90% bootstrap 区间：[{lower:.4f}, {upper:.4f}]")
    lines.append(f"oracle 测试期末金额：{report['oracle_test_final_money']:.2f} 元")
    lines.append(f"动量 测试期末金额：{report['momentum_test_final_money']:.2f} 元")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permutations", type=int, default=5000)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    report = evidence_report(args.permutations, args.bootstrap, args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_report(report))


if __name__ == "__main__":
    main()
