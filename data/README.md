# 本书独立数据目录

> 本书的数据随教材仓库提供。**不依赖个人量化项目、私有数据库、外部行情盘符或交易账户**。克隆教材即可验证现有练习。

## 核心数据包

| 类型 | 路径 | 用途 |
|---|---|---|
| 真实历史固定行情 | [real_a_share](real_a_share/README.md) | 四只 A 股各 117 根 2024 年不复权日线，固定来源与 SHA；只能做价格算术和限定样本描述 |
| 合成多期研究案例 | [story](story/README.md) | A/B/C/D、60 期共 240 条虚构证券期；训练、验证、回测与模型选择逻辑 |
| 合成 PIT/修订事件 | [teaching](teaching/README.md) | A/B/C 成员版本、财报修订、披露/入库时间和标签可用时点 |

所有正式输入与用途在 [教材数据清单](teaching/manifest.json) 中有明确 `dataset_id` 和 `evidence_grade`。**真实四股行情不等于完整历史 PIT 或全市场回测数据**；合成事件不等于真实公告/行情。

## 复算与维护

~~~bash
python scripts/verify_teaching_datasets.py
python examples/advanced_pit_intake_lab.py --json
python examples/advanced_real_evidence_audit.py --json
~~~

数据清单与快照在 Git 里固定；教材 CI 不会自动下载市场数据，不需要任何个人的本地数据库路径。

如需要扩充新的 A 股**教学数据快照**，可使用本仓库的 [AKShare 采集程序](../scripts/collect_real_a_share.py) 创建新的版本，但必须事前检查上游许可、来源与字段单位，记录每次采集的时间、快照校验和、异常记录和是否可以公开再分发。重复下载同一历史日期的数据不能保证字节相同，因此不能静默替换本书旧的教学快照。

## 专业研究需要什么（但不作为当前教材的隐藏依赖）

真实大截面的动态证券身份、历史上市/退市、当时可得的财务修订、行业成员、停牌/涨跌停、公司行为与实盘成本等，都需公开清晰的数据合同和验证；**教材未提供这些时，章节应明确是教学示范，不能以原本不存在的私有数据充当实证证据**。

[第二卷数据规范](../advanced/volume-2/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md)。
