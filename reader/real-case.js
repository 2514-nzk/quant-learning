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

  function averageRanks(values) {
    const indices = values.map((_,i)=>i).sort((a,b)=>values[b]-values[a]);
    const ranks = Array(values.length);
    for(let lo=0;lo<indices.length;){
      let hi=lo+1;
      while(hi<indices.length && values[indices[hi]]===values[indices[lo]])hi++;
      for(let j=lo;j<hi;j++)ranks[indices[j]]=(lo+hi+1)/2;
      lo=hi;
    }
    return ranks;
  }

  function rankIc(rows) {
    if (!Array.isArray(rows) || rows.length !== 4 || new Set(rows.map(r=>r.symbol)).size!==4 ||
        !rows.every(r=>Number.isFinite(r.mom5)&&Number.isFinite(r.forward_return))) {
      throw new Error("这一练习需要同一期四只股票的完整数据。");
    }
    const x=averageRanks(rows.map(r=>r.mom5)),y=averageRanks(rows.map(r=>r.forward_return));
    const mx=x.reduce((a,b)=>a+b,0)/4,my=y.reduce((a,b)=>a+b,0)/4;
    const xx=x.reduce((a,b)=>a+(b-mx)**2,0),yy=y.reduce((a,b)=>a+(b-my)**2,0);
    if(!xx||!yy)return null;
    return x.reduce((sum,v,i)=>sum+(v-mx)*(y[i]-my),0)/Math.sqrt(xx*yy);
  }

  function sensitivity(sample, direction, count, bps) {
    assertValid(sample);
    if(!["momentum","reversal"].includes(direction)||!Number.isInteger(count)||count<1||count>4||
       !Number.isFinite(bps)||bps<0||bps>100)throw new Error("实验参数超出课堂范围");
    const sign=direction==="momentum"?1:-1,cost=bps/10000;
    const rows=sample.rounds.map(round=>{
      const sorted=[...round.rows].sort((a,b)=>sign*(b.mom5-a.mom5)||a.symbol.localeCompare(b.symbol));
      const selected=sorted.slice(0,count);
      const gross=selected.reduce((a,b)=>a+b.forward_return,0)/count;
      const benchmark=sorted.reduce((a,b)=>a+b.forward_return,0)/4;
      const ic=rankIc(round.rows);
      return {signal:round.signal_date,selected:selected.map(r=>r.name),gross,benchmark,ic:ic===null?null:sign*ic};
    });
    function stats(values,name){
      const ics=values.map(v=>v.ic).filter(Number.isFinite);
      const compound=fn=>values.reduce((a,v)=>a*(1+fn(v)),1)-1;
      return {name,periods:values.length,definedIc:ics.length,
        meanIc:ics.length?ics.reduce((a,b)=>a+b,0)/ics.length:null,
        gross:compound(v=>v.gross),netProxy:compound(v=>v.gross-cost),
        benchmarkProxy:compound(v=>v.benchmark-cost)};
    }
    return {...stats(rows,"全部"),rows,blocks:[stats(rows.slice(0,10),"前10期"),stats(rows.slice(10,14),"中4期"),stats(rows.slice(14),"后4期（已公开）")]};
  }

  function summarize(rounds) {
    if (!Array.isArray(rounds) || rounds.length === 0) {
      throw new Error("没有可计算的历史观察期。");
    }
    let strategy = 1, baseline = 1, sumIc = 0, definedIc = 0;
    for (const round of rounds) {
      const returns = sortMomentum(round.rows).map((x) => x.forward_return);
      strategy *= 1 + (returns[0] + returns[1]) / 2;
      baseline *= 1 + returns.reduce((a, b) => a + b, 0) / 4;
      const ic = rankIc(round.rows);
      if(ic!==null){sumIc+=ic;definedIc++;}
    }
    return {
      periods: rounds.length,
      meanIc: definedIc ? sumIc / definedIc : null,
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
      lines.push(name + "：" + s.periods + "期｜平均RankIC " + (s.meanIc===null?"未定义":signed(s.meanIc, 3)) +
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

  const api = { run, rankIc, summarize, sensitivity };
  root.QuantRealCase = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof self !== "undefined" ? self : globalThis);
