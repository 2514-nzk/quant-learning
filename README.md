# A 股量化研究入门：从问题到样本外证据

这是一本面向有炒股经验、想从零学量化的读者的中文教材。**主阅读路线改为四只真实 A 股的历史日 K 线：贵州茅台、寒武纪、宁德时代、比亚迪。** 先学会从行情里算收益率、MA5、组合和基准，再走向因子评价、模型与研究审计。

[打开在线阅读器](https://2514-nzk.github.io/quant-learning/) · [完整章节目录](教程/README.md) · [第一课：四只真实股票的选股](教程/真实_起步一课.md)

主线以 **2024-06-21 收盘后选股、06-24 开盘观察买入、06-28 收盘观察卖出**为贯穿案例，使用真实不复权日线演算；另用 18 个不重叠时间段练习历史比较。**知名股票是事后挑选的小样本，所有数字仅用于教学，不表示已经发现有效的交易策略。**

原来四只虚构股票、60 期合成数据和模型实验仍保留在仓库中作为**旧版模拟研究资料**，不会与这套真实价格的收益混用。模型、因子诊断和数据工程的老脚本仍可单独复现，不能当成这四只真实 A 股的实证成绩。

## 阅读路径

| 阶段 | 章节 | 要回答的问题 |
|---|---|---|
| 起步线 | 两节真实股票起步课 | 从真实日K线做一次选股，怎样避免偷看未来？ |
| 第一循环 | 第 1–2 章 | 这笔收益算不算本事？ |
| 第二循环 | 第 3–8 章 | 数据和因子可不可信？ |
| 第三循环 | 第 9–10 章 | 信号能不能变成钱？ |
| 第四循环 | 第 11–14 章 | 模型有没有增加信息？ |
| 收尾 | 第 15–16 章 | 结论能不能重做？ |

模型练习用固定的 60 期教学数据；原有七特征工程案例和月度三因子项目转入工具与参考区，作为主线之后的扩展。来源课程的模块映射见[课程融合与来源对照](教程/附录A_课程融合与来源对照.md)。

## 运行主线的真实股票练习

~~~powershell
python examples/real_stock_learner.py
~~~

它只读取已冻结的2024年四只股票行情快照，输出这套固定课堂规则的选择、理论资金和分期排名评价。图片及CSV位于 [data/real_a_share](data/real_a_share)。不需要另外联网拉行情。

## 旧版模拟研究脚本（不属于真实股票主线）

以下命令只复现以前四只虚构股票与60期合成数据的教学实验，**不要把其输出理解为茅台、寒武纪、宁德时代、比亚迪的真实策略结果**。



在项目目录运行，基础演算无需额外依赖：

```powershell
python examples/first_quant_experiment.py
python examples/story_research.py
python examples/story_evidence.py
python examples/research_audit_lab.py  # 标准库可运行：时点、边界和 RankIC 审计
python examples/factor_diagnostics_lab.py  # 单因子逐期诊断、成本和 ICIR
python examples/model_selection_audit.py  # 核对保存的模型试验和验证选参
python examples/real_kline_lab.py --symbol 000001  # 读真实 AKShare 日线并算 MA5、MOM5
```

安装 `requirements.txt` 中的依赖后，可以运行后半本的模型练习并保存报告：

```powershell
pip install -r requirements.txt
python examples/story_research.py --models --output outputs/story/report.json
```

输入、已执行的参考输出、数据构造与费率约定见[故事数据说明](data/story/README.md)。所有数字均为人工教学数据，模型成绩不代表真实市场表现。

## 扩展：运行原五日工程案例

这个入口使用独立的较大日频面板、七个特征和工程配置，结果与正文故事分别记录：

在项目根目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.run_demo
```

运行完成后，结果位于 `outputs/demo/<run_id>/`。`outputs/demo/latest.txt` 保存最近一次运行编号；也可以先设置 `QUANT_RUN_ID`，例如 `$env:QUANT_RUN_ID='ridge_ablation_001'`。每次实验使用独立目录，避免覆盖旧结果。

- `sample.csv`：特征、标签和样本元数据
- `predictions.csv`：每个样本外日期的模型预测
- `backtest_<model>.csv`：各模型 Top-N 组合的逐期收益、成本、净值和延迟退出统计
- `rank_ic_<model>.csv`、`grouped_returns_<model>.csv`：预测评价明细
- `metrics.json`：RankIC、分组收益、Sharpe、最大回撤、换手和成本后结果
- `report.md`：自动生成的研究摘要
- `config_used.json`、`run_manifest.json`、`data_source.json`：本次配置、环境版本、样本范围和数据来源

教学回测使用与标签一致的非重叠 5 日持有期，并同时报告等权股票池基准和主动收益。它仍是简化回测，不含五组重叠持仓、逐笔成交和完整风格归因。合成数据不是投资数据，也不能证明任何策略有效；真实 A 股数据的最低字段和缺口见 [`data/README.md`](data/README.md)。

如果本地已有只读 DuckDB 快照，可以把 `QUANT_DUCKDB_SNAPSHOT` 设为 `current.json` 的路径，再运行真实数据示例：

```powershell
$env:QUANT_DUCKDB_SNAPSHOT='D:/duckdb_data/xc_tushare_data.snapshots/current.json'
python -m src.run_duckdb_demo
```

未设置环境变量时，脚本使用 `config/duckdb_config.yaml` 中的默认路径。它读取快照，不会写入或锁定主数据库。真实结果位于 `outputs/duckdb_demo/<run_id>/`，最近一次编号见同目录的 `latest.txt`。

## 项目结构

```text
教程/                       教材正文、阅读指南和参考材料
examples/                   Python 与数学统计练习脚本
data/story/                 正文固定题目、价格指数与模型参考输出
src/                        可运行的教学版研究代码
config/research_config.yaml 统一研究规格
data/README.md              真实数据需求、字段契约和缺口
templates/                  研究规格、研报复现、因子定义、报告与审计模板
outputs/                    自动生成的运行结果
```

本项目仅用于机器学习和量化研究方法教育，不构成投资建议、收益承诺、个股推荐或实盘操作指引。真实交易还需要可靠的数据供应、规则校验、容量评估、风险管理、执行和合规流程。
