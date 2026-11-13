# 第二卷 · 附录 C｜历史股票池与数据源覆盖审计

> **状态：真实四股 OHLC 文件完整性已可复核；没有完整 A 股历史母体或可核实的历史 PIT 来源，因此全市场覆盖率和可交易有效性均未建立。**

本附录连接 [第 05 章 PIT](05_pit_data.md)、[第 06 章标签](06_labels_splits.md)、[第 07 章因子工程](07_factor_engineering.md)。目标是明确区分**四股教学样本内部的完整程度**与**A 股历史全市场的数据覆盖**。

## 1. 现有真实数据到底覆盖多少？

[仓库 AKShare 采集清单](../../data/real_a_share/manifest.json) 标明，2026-11-11 采集了贵州茅台、寒武纪、宁德时代、比亚迪的 2024-01-02 至 2024-06-28 的不复权日线。每只 117 条，总计 **468 条已观察股票日**。四股日期并集和交集均为 **117 个已观察日期**。

因此，本样本的“内部日期重合比例” = 468/(4×117) = 100%；**这不是 A 股全市场覆盖率、官方交易日历覆盖率、历史 PIT 证明，也不是幸存者偏差检查**。真实研究的分母需来自按历史时点有效的证券母表，不能用已经下载了价格的四只股票替代。

程序会明确输出：

~~~text
observed_security_count: 4
observed_security_sessions: 468
observed_date_union_sessions: 117
common_observed_date_count: 117
sample_internal_coverage_fraction: 1.0
full_market_denominator: null
full_market_coverage_percent: null
official_exchange_calendar_verified: false
historical_pit_verified: false
~~~

**研究禁区**：不能凭本地样本内部覆盖 100% 推断市场全覆盖 100%。117 个已观察日期，也不是官方已确认的交易日历全集。

## 2. 八类来源分开审计

| 来源层 | 生产研究需要的证据 | 当前仓库可验证范围 |
|---|---|---|
| SECURITY_MASTER | 全部历史上市/退市及证券身份变动 | 未提供 |
| HISTORICAL_MEMBERSHIP | 历史成分、成员区间和修订 | 未提供 |
| INDUSTRY_PIT | 申万分类体系及成员的历史可得版本 | 未提供 |
| OHLC | 历史价格、来源、版本、时点与公司行为 | **四股 CSV 的 SHA-256 与 OHLC 算术**；历史源接收时点未证实 |
| CORPORATE_ACTIONS | 分红、复权、除权版本 | 未提供 |
| DISCLOSURES_AND_REVISIONS | 披露、更正、撤回和历史消息日志 | 未提供 |
| EXCHANGE_SESSIONS | 正式交易所日历及例外休市 | 未提供 |
| EXECUTION_STATUS | 停牌、风险警示、价幅、交易权限和成交 | 未提供 |

这里的“未提供”只指**当前公开教材仓库**，不是断言外部数据供应商不存在这些资料。

## 3. 可复现审计：真实文件与合成历史版本

[完整 Python 程序](../../examples/advanced_universe_coverage_lab.py) 仅使用标准库，可对真实四股文件、合成版历史参考集或用户本地 JSON 进行核验。

### A. 固定四股真实行情（不需要网络）

~~~bash
python examples/advanced_universe_coverage_lab.py --real-teaching --json
~~~

首先核对 manifest/CSV SHA-256 与 OHLC，再枚举四个证券各自的真实已观察日期集合、并集、交集和缺失日期；对未建立的全市场分母返回 null。没有持有过证券母表、行业历史成员或官方日历时，相关证据门不会变成 PASS。

### B. 合成 A/B/C 两期历史成员与价格（非真实行情）

~~~bash
python examples/advanced_universe_coverage_lab.py --json
python -m unittest discover -s tests -p "test_advanced_universe_coverage_lab.py" -v
~~~

演示参考集是 A、B、C，决策日设为 2024-03-20 与 2024-04-11。3 月：A 的成员身份和价格按人工设定已可得；B 成员来源尚晚到，状态是 **UNKNOWN**，不是“不合格”；C 成员区间已结束。4 月：A 的更正事件已可得并变为不合格，B 变为已知合格且有价。

若某日价格记录在决策截止之后才可得，应报告 **LATE_OR_UNAVAILABLE_AT_DECISION**；若价格没有记录，应报告 **MISSING_PRICE_RECORD**；不能把两者都填 0，也不能静默删除缺失者再计算覆盖率。

参考集上的可判定成员比例：

\[
q_t^{reference}=\frac{\#\{i\in R_t:\text{成员身份在决策时可判定}\}}{|R_t|}.
\]

但即使 q=100%，只要 R 不是已核实的历史全市场证券清单，也只能说“声明参考集合”的内部可判定程度。真实市场的全量分母仍为 null。

### C. 本地数据候选合同（不上传仓库）

~~~bash
python examples/advanced_universe_coverage_lab.py --input /本地路径/universe_coverage.json --json
python examples/advanced_universe_coverage_lab.py --real-teaching --output outputs/universe_coverage_v1.json
~~~

本地 JSON 包含 `data_kind`、`universe_scope`、`reference_source`、`calendar_source`、`snapshots`（信号日、带时区的决策时刻、参考证券列表）、`membership_events`、`facts`、`prices`，以及可选 `required_fact_fields`。

各成员/事实/价格版本需标明 source_ref、revision_id、声明的 SHA-256 和 source_published_at/ingested_at/available_at。程序检查格式、时序、重复记录与已知/迟到/缺失，**但不验证供应商原始文件内容是否真的对应这些元数据**。因此无论本地声明多完整，都不会自动把报告升级为已证实历史 PIT。报告写入新文件时拒绝覆盖旧报告。

## 4. 本轮具体的失败门禁

- 重复参考证券、重复价版本、非法价格、缺来源或缺时区，不允许静默通过；
- 决策时未到达的成员/财务修订不能回填；无已知成员身份与明确不合格必须区分；
- 迟到价格与根本缺失分开统计，避免剔除失败样本后制造虚假高覆盖；
- 用户提供的“历史股票池候选”**不等于**已经核实的全市场母体；
- 真实四股快照未带真实历史供应商消息、行业 PIT、公司行为及执行数据，故禁止推出 Alpha 或净收益结论。

## 5. 下一步怎样接入真正的历史全市场数据？

首先取得具授权的交易所历史证券母表、有效上市/退市及停复牌时间、官方交易日历、行业版本与来源事件日志。以此形成 **权威历史分母**，再将全量价量及财务数据按 decision_at 做 as-of 对照；对每个年份/板块/行业报告缺失、晚到、未知与实际不合格数量。之后才开始第 07–11 章的因子、模型和独立 OOS 工作。

**本轮成果是“覆盖审计方法 + 真实四股来源盘点”，不是“真实全市场 PIT 已接通”。**

返回 [第二卷目录](README.md) · [审校台账](REVIEW_BACKLOG.md)。
