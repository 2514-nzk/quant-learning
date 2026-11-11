# A 股量化研究入门：从问题到样本外证据

这是一本面向初学者的量化研究教材。它只做一件事：陪你从 8,000 元虚拟资金出发，完成一次能复查的选股研究，再逐步检查这笔研究哪里可能错。

正文用四只虚构股票 A、B、C、D 贯穿全书。第一笔在起步课里用手算完成，第二课翻译成 Python；之后每一章只增加一个需要解决的问题。阅读顺序见[阅读指南](教程/00_学习路线.md)，完整目录见[教材目录](教程/README.md)，也可以直接打开[在线阅读器](https://2514-nzk.github.io/quant-learning/)。从零基础到研究级的四阶学习与项目要求见[进阶实战路线](教程/进阶实战_从教学数据到研究级流程.md)。如果是第一次接触量化，建议先读[用 8,000 元起步的阅读指南](教程/00_学习路线.md)，顺着章节学习；[16 道带详细答案的小题](教程/00h_零基础16道小题.md)放在全书收尾，当作分阶段复习，不必起步时就全部做完。

如果已学到单因子和机器学习，推荐继续读[深度专题 A：因子研究](教程/专题A_单因子到稳健性研究.md)和[深度专题 B：模型验证](教程/专题B_机器学习验证与增量检验.md)，两篇都有不依赖第三方库的审计脚本。

## 阅读路径

| 阶段 | 章节 | 要回答的问题 |
|---|---|---|
| 起步线 | 两节起步课 | 一次选股怎样算清楚？ |
| 第一循环 | 第 1–2 章 | 这笔收益算不算本事？ |
| 第二循环 | 第 3–8 章 | 数据和因子可不可信？ |
| 第三循环 | 第 9–10 章 | 信号能不能变成钱？ |
| 第四循环 | 第 11–14 章 | 模型有没有增加信息？ |
| 收尾 | 第 15–16 章 | 结论能不能重做？ |

模型练习用固定的 60 期教学数据；原有七特征工程案例和月度三因子项目转入工具与参考区，作为主线之后的扩展。来源课程的模块映射见[课程融合与来源对照](教程/附录A_课程融合与来源对照.md)。

## 重做书里的研究

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
