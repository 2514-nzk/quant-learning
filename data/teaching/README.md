# 教材专用数据集（与个人量化研究数据完全解耦）

> **课程数据版本：course-datasets-v1。** 本文件夹与仓库的 `data/real_a_share`、`data/story` 一起构成教材独立数据包；不依赖任何私人研究数据库、证券账户或个人策略输出。

## 已随教材提供的五套独立数据

| 编号 | 实际数据 | 类型 | 用途 |
|---|---|---|---|
| `a-share-real-four-v1` | 2024-01-02—2024-06-28 四只真实 A 股，每只 117 根不复权日线 | **真实历史报价的固定教学样本** | K 线、收益、MOM5、排序、四股 18 期描述性分析 |
| `story-synthetic-v1` | 虚构 A/B/C/D 共 60 期（240 个证券期），带模型选择参考输出 | **明确标记合成** | 全流程研究/回测/模型比较/反例 |
| `pit-events-synthetic-v1` | 虚构 A/B/C 的 4 个成员版本、3 个财务记录版本和 2 条标签 | **明确标记合成** | 时间可得性、财报修订、未知成员、Purge 边界 |
| `volume3-weekly-synthetic-v1` | 16 个虚构周度时点、每期四行业和八股票，两套人工行业版本 | **明确标记合成** | 第三卷 01–04 策略合同、状态、行业、反转和成本代理 |
| `volume3-microcap-synthetic-v1` | 12 个虚构证券、3 个教学时点，含财务可得时间、通用评分、流动性及交易受阻状态 | **明确标记合成** | 第三卷 05 微盘资格、候补与持仓状态教学 |

完整机器可读元数据在 [manifest.json](manifest.json)，PIT 事件数据在 [pit_events_v1.json](pit_events_v1.json)。数据文件**随课程仓库一起版本化**；阅读与基础测试无需访问任意个人数据库。

## 可重复运行

在仓库根目录：

~~~bash
python scripts/verify_teaching_datasets.py
python examples/advanced_pit_intake_lab.py --json
python examples/advanced_real_evidence_audit.py --json
python examples/volume3_strategy_lab.py --json
python -m unittest discover -s tests -p "test_teaching_dataset_contract.py" -v
~~~

第一条核查真实四股 CSV 的 SHA-256、60 期虚构数据、PIT 事件和第三卷周度人工数据；第二条从**仓库里的固定 PIT 事件 JSON**读取演示，不采用个人本地财务流水；第三条只对教材四股样本做**回顾性审计**。

如确需**重新采集一份新的教材市场快照**，可使用 `scripts/collect_real_a_share.py` 和 AKShare。但必须记录来源/下载时刻/版本/复权口径/SHA-256，提交新版本前审查原有快照是否被覆盖；**重新下载的价格不一定与旧教材数字完全一致**。生产发布与 CI 使用仓库固定版本，不实时下载行情。

## 证据与研究边界

- **真实价 ≠ 完整历史 PIT**：四只真实股票是事后命名的演示样本，不代表全市场或独立样本外测试；数据没有分红、交易费用、真实成交/排队或完整公司行为证据。
- **合成 PIT ≠ 真实历史公告**：`source_published_at`、`ingested_at` 等是教学设计的模拟事件，绝不能描述成真实供应商日志。
- **未提供完整全市场历史数据库**：如果以后扩展教学数据，需建立**本仓库单独的数据版本、合法可分发的公开来源与来源证据**，不能将个人策略数据库复制、链接或假定可访问。
- **资料许可**：新增真实市场数据采集前核实上游数据许可。公开仓库不存放受限的私有行情/证券账户/原始个人研究数据。

## 分卷使用协议

第一卷使用真实四股价格与单独的合成故事案例。第二卷使用合成 PIT、合成多资产/模型实验和四股描述性统计；**用于解释方法和失败机制，不冒充市场统计优势**。第三卷第 01–04 章使用 volume3-weekly-synthetic-v1，第 05 章使用 volume3-microcap-synthetic-v1 完成可复算方法教学；该人工周度情景不代表真实交易所日历、实际申万行业或独立市场 OOS。后续策略依然需要各自合法来源、版本和研究合同。

[返回教材数据总览](../README.md) · [第二卷数据说明](../../advanced/volume-2/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md)。
