# 第二卷｜专业量化研究方法

> **状态：14/14 章教学版 v1 已完成内部方法、公式与例题校审；教材数据独立封存。仍不具备完整真实 PIT、独立市场 OOS 或外部专业审稿认证。**

本卷从量化概念转向严谨研究：数据时点、统计推断、样本外、组合交易与可复现性。教材与个人量化研究数据池**相互独立**。

## 章节路线（01–14）

| 章 | 主题 | 要回答的问题 | 状态 |
|---|---|---|---|
| 01 | [第 01 章｜研究问题与可证伪实验合同](01_research_protocol.md) | 怎样在看结果前规定何时承认假设失败？ | 教学版 v1 / 实验可复算 |
| 02 | [第 02 章｜数学、概率统计与优化基础](02_math_statistics.md) | 理解因子、回归与组合优化需要什么数学？ | 教学版 v1 / 实验可复算 |
| 03 | [第 03 章｜金融时间序列与计量方法](03_time_series.md) | 自相关、异方差和非平稳性怎样改变统计结论？ | 教学版 v1 / 实验可复算 |
| 04 | [第 04 章｜A 股制度、时间轴与信息门禁](04_market_rules.md) | 不同证券与历史日期的规则如何影响研究？ | 教学版 v1 / 实验可复算 |
| 05 | [第 05 章｜全市场 PIT 数据工程与动态股票池](05_pit_data.md) | 怎样只使用当时真正存在和可得的数据？ | 教学版 v1 / 实验可复算 |
| 06 | [第 06 章｜标签、时间切分、Purge 与 Embargo](06_labels_splits.md) | 标签何时形成，训练样本何时必须清除？ | 教学版 v1 / 实验可复算 |
| 07 | [第 07 章｜因子工程、表达式与中性化](07_factor_engineering.md) | 如何从经济假设得到不泄漏的可复算因子？ | 教学版 v1 / 实验可复算 |
| 08 | [第 08 章｜单因子评价、统计推断与稳健性](08_factor_validation.md) | 正的 RankIC 能证明什么，又不能证明什么？ | 教学版 v1 / 实验可复算 |
| 09 | [第 09 章｜多因子合成、风格暴露与增量](09_factor_combination.md) | 新增因子是在补充信息还是重复投票？ | 教学版 v1 / 实验可复算 |
| 10 | [第 10 章｜监督学习、排序学习与模型解释](10_machine_learning.md) | 回归、分类和学习排序到底优化什么？ | 教学版 v1 / 实验可复算 |
| 11 | [第 11 章｜严格 OOS、漂移与模型增量检验](11_oos_drift.md) | 调参后还有多少独立证据？ | 教学版 v1 / 实验可复算 |
| 12 | [第 12 章｜风险模型、组合优化与约束](12_portfolio_optimization.md) | 从预测分数到目标持仓需处理哪些风险？ | 教学版 v1 / 实验可复算 |
| 13 | [第 13 章｜成交仿真、交易成本与回测状态机](13_backtest_execution.md) | 研究信号如何变成真实可持有的仓位？ | 教学版 v1 / 实验可复算 |
| 14 | [第 14 章｜可复现研究工程与综合项目](14_reproducible_capstone.md) | 第三方怎样独立复算并判定一个研究结果？ | 教学版 v1 / 实验可复算 |

## 教学版 v1 质量收口

- **附录 D（全卷内部质量校审与术语表）**：14 章逐章核查、公式/术语/习题标准、统一证据等级和可运行校验命令。
- **附录 B（逐章校审台账）**：已通过的内部教材项与真实市场研究、外部同行评阅严格区分。
- **本版教材目标是可读、可算、可独立运行**；内部校审通过不等于宣称获得全市场可交易 Alpha，也不意味着法律/学术外部终审完成。

## 本卷的数据与实验

- [教材专用数据总览](../../data/teaching/README.md)：三个冻结数据集及可复核的来源标签；任何读者克隆仓库即可练习。
- [附录 A｜真实四股价格证据审计](REAL_DATA_EVIDENCE_REVIEW.md)：有真实历史报价，但没有全市场 PIT 或独立 OOS 证明。
- [附录 B｜教学版校审与外部待办](REVIEW_BACKLOG.md)：14 章内部质量核对及真正需要外部验证的项目。
- [附录 C｜教材数据集与复现规范](HISTORICAL_UNIVERSE_SOURCE_AUDIT.md)：三套独立课程数据的用途、输入合同、缺失语义、复现与扩充边界。
- [附录 D｜全卷质量校审与术语表](QUALITY_REVIEW_V1.md)：教学版 v1 内部核对清单、统一口径和外部验证边界。

本卷的 `advanced_protocol_pit_lab.py`、`advanced_factor_research_lab.py` 和 `advanced_model_validation_lab.py` 使用合成教学输入；`advanced_pit_intake_lab.py` 默认读取仓库封存的 PIT 事件 JSON。无需借助作者的其他量化项目，也不会偷偷读取未发布的数据库。

## 已有章节的实验入口

- [01 研究合同](01_research_protocol.md)：时间合同、严格验证边界及失败标准。
- [02–04 数学、时间序列与历史交易规则实验](../../examples/advanced_foundations_market_rules_lab.py)：手算 OLS/Ridge/矩阵、AR(1)、HAC、区块 Bootstrap、2026-07-06 沪深风险警示规则版本与跨境时间门禁。[配套测试](../../tests/test_advanced_foundations_market_rules_lab.py)。
- [05 PIT 数据](05_pit_data.md)：历史成员、财务版本与 as-of 选择。
- [研究合同 / PIT 实验源码](../../examples/advanced_protocol_pit_lab.py) · [配套测试](../../tests/test_advanced_protocol_pit_lab.py)。
- [06–08 因子研究实验源码](../../examples/advanced_factor_research_lab.py)：前向 Purge、当期中性化、逐期 IC、HAC、区块 Bootstrap、分组和 Holm 演示。 [配套测试](../../tests/test_advanced_factor_research_lab.py)。
- [09–11 模型选择和时间验证实验](../../examples/advanced_model_validation_lab.py)：六候选基线、Ridge/成对排序、开发期消融、冻结选择、逐期可用标签重训及事后漂移。[配套测试](../../tests/test_advanced_model_validation_lab.py)。
- [12–14 组合、执行和审计实验](../../examples/advanced_portfolio_execution_lab.py)：合成风险协方差、离散权重、整手/T+1、拒单与部分成交、现金/NAV 审计和版本指纹。[配套测试](../../tests/test_advanced_portfolio_execution_lab.py)。

**部分实验使用人工数据，另有四股真实历史 OHLC 的限定样本描述；二者都不构成完整历史 PIT、独立 OOS 或可交易 Alpha 证据。**

## 统一交付标准

每章完成时都应包含：研究问题与假设、公式/算法、数据字典与 PIT 检查、可运行 Python、对照和严格样本外、成本/风险/失败案例、习题与来源。未做实验时不得填造结果。

## 可以整理进来的既有材料

- [研究规格与字段](../../教程/参考_研究规格与字段.md)
- [数据标签实现与审计](../../教程/参考_数据标签实现与审计.md)
- [因子研究完整方法](../../教程/参考_因子研究完整方法.md)
- [机器学习验证专题](../../教程/专题B_机器学习验证与增量检验.md)
- [从教学到研究级流程](../../教程/进阶实战_从教学数据到研究级流程.md)

这些链接指向研究素材，**不代表已经完成新章内容或通过审计**。

返回 [三卷总览](../README.md) · [写作与实验规范](../AUTHORING_GUIDE.md)。
