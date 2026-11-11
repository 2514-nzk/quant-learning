/* Calculate the book's fixed real-market teaching data without an external Python runtime. */
(function (root) {
  "use strict";

  function assertValid(sample) {
    if (!sample || !Array.isArray(sample.rounds) || sample.rounds.length === 0) {
      throw new Error("课堂历史数据不完整，请刷新页面后重试。");
    }
    if (!Number.isFinite(sample.budget) || sample.budget <= 0) {
      throw new Error("课堂资金数据有误，请刷新页面后重试。");
    }
    for (const round of sample.rounds) {
      if (!round || !Array.isArray(round.rows) || round.rows.length !== 4 ||
          !round.rows.every((item) => item && typeof item.name === "string" &&
            typeof item.symbol === "string" && Number.isFinite(item.mom5) &&
            Number.isFinite(item.forward_return))) {
        throw new Error("部分股票历史数据不完整，请刷新页面后重试。");
      }
    }
  }

  function sortMomentum(rows) {
    return [...rows].sort((a, b) => b.mom5 - a.mom5 || a.symbol.localeCompare(b.symbol));
  }

  function rankIc(rows) {
    if (!Array.isArray(rows) || rows.length !== 4) {
      throw new Error("这一练习需要同一期四只股票的完整数据。");
    }
    const predicted = sortMomentum(rows);
    const realized = [...rows].sort((a, b) =>
      b.forward_return - a.forward_return || a.symbol.localeCompare(b.symbol));
    if (new Set(rows.map((r) => r.forward_return)).size !== 4 ||
        new Set(rows.map((r) => r.mom5)).size !== 4) {
      throw new Error("当前数据出现并列名次，需要改用平均名次计算。");
    }
    const rank = new Map(realized.map((r, i) => [r.symbol, i + 1]));
    const squared = predicted.reduce((sum, r, i) => {
      const diff = (i + 1) - rank.get(r.symbol);
      return sum + diff * diff;
    }, 0);
    return 1 - 6 * squared / 60;
  }

  function summarize(rounds) {
    if (!Array.isArray(rounds) || rounds.length === 0) {
      throw new Error("没有可计算的历史观察期。");
    }
    let strategy = 1, baseline = 1, sumIc = 0;
    for (const round of rounds) {
      const returns = sortMomentum(round.rows).map((x) => x.forward_return);
      strategy *= 1 + (returns[0] + returns[1]) / 2;
      baseline *= 1 + returns.reduce((a, b) => a + b, 0) / 4;
      sumIc += rankIc(round.rows);
    }
    return {
      periods: rounds.length,
      meanIc: sumIc / rounds.length,
      strategyPct: (strategy - 1) * 100,
      baselinePct: (baseline - 1) * 100,
    };
  }

  function number(value, digits = 2) {
    return Number(value).toLocaleString("zh-CN", {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
  }

  function signed(value, digits = 2) {
    return (value >= 0 ? "+" : "") + number(value, digits);
  }

  function run(sample) {
    assertValid(sample);
    const rounds = sample.rounds;
    const latest = sample.intro && Array.isArray(sample.intro.rows)
      ? sample.intro : rounds[rounds.length - 1];
    const sorted = sortMomentum(latest.rows);
    const selected = sorted.slice(0, 2);
    const topReturn = selected.reduce((a, x) => a + x.forward_return, 0) / 2;
    const allReturn = sorted.reduce((a, x) => a + x.forward_return, 0) / 4;
    const budget = sample.budget;
    const lines = [
      "四只真实 A 股｜2024 年历史日 K 线教学演算",
      "决策：" + latest.signal_date + "收盘后｜观察买入：" + latest.entry_date +
        "开盘｜观察结束：" + latest.exit_date + "收盘",
      "",
      "股票（过去5日涨幅 → 后来观察收益）",
    ];
    for (const row of sorted) {
      lines.push(row.name + "（" + row.symbol + "）：" +
        signed(row.mom5 * 100) + "% → " + signed(row.forward_return * 100) + "%");
    }
    lines.push(
      "",
      "按过去5日涨幅选前2名：" + selected.map((row) => row.name).join("、"),
      "各分配" + number(budget / 2, 0) + "元，理论期末：" +
        number(budget * (1 + topReturn)) + "元",
      "四只等权对照，理论期末：" + number(budget * (1 + allReturn)) + "元",
    );
    if (latest.lot_shares && Number.isFinite(latest.lot_uninvested_cash)) {
      let ending = latest.lot_uninvested_cash;
      for (const item of selected) {
        const shares = latest.lot_shares[item.symbol] ?? 0;
        if (!Number.isInteger(shares) || shares < 0 ||
            !Number.isFinite(item.exit_close)) throw new Error("买入股数记录有误。");
        ending += shares * item.exit_close;
      }
      lines.push("按课堂整股数量及剩余现金计算：" + number(ending) + "元（未扣费）");
    }
    lines.push("", "共 " + rounds.length + " 个历史观察期，按时间分段：");
    for (const [name, values] of [
      ["前10期（学习）", rounds.slice(0, 10)],
      ["中4期（比较）", rounds.slice(10, 14)],
      ["后4期（留出演示）", rounds.slice(14)],
    ]) {
      if (!values.length) continue;
      const s = summarize(values);
      lines.push(name + "：" + s.periods + "期｜平均RankIC " + signed(s.meanIc, 3) +
        "｜选股复利 " + signed(s.strategyPct) + "%｜四股等权 " +
        signed(s.baselinePct) + "%");
    }
    lines.push(
      "",
      "这里直接读取已保存的真实历史行情计算，没有执行 Python 程序。",
      "仅用于练习：不计分红、费用及真实委托成交；四只知名股票不能代表全市场。",
    );
    return lines.join("\n");
  }

  const api = { run, rankIc, summarize };
  root.QuantRealCase = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof self !== "undefined" ? self : globalThis);
