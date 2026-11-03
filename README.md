# A 股量化研究入门：从问题到样本外证据

这是一本面向初学者的量化研究教材，按研究问题、数据、因子、组合、模型比较与复现组织为五编、十六章。正文用一笔 8,000 元的模拟研究串起概念、手算与代码，保留尝试、失败和修正过程。阅读顺序见[教材目录](教程/README.md)，也可以直接打开[在线阅读器](https://2514-nzk.github.io/quant-learning/)。

初次接触量化或代码时，先完成目录中的两节起步课：用四只虚构股票手算选择与收益，再逐行读懂对应的 Python。pandas、数学统计和完整实现资料按问题查阅，正文会逐步引入它们。

正文使用固定的虚构教学数据，手算与模型表都有配套运行入口，并加入先猜后展开的答案和资金曲线。原有七特征工程案例、月度三因子项目和完整方法转入参考区，作为主线之后的扩展。来源课程的模块映射见[课程融合与来源对照](教程/附录A_课程融合与来源对照.md)。

## 重做书里的研究

在项目目录运行，基础演算无需额外依赖：

```powershell
python examples/first_quant_experiment.py
python examples/story_research.py
python examples/story_evidence.py
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
教程/                       教材正文、参考资料和规则附录
examples/                   Python 与数学统计练习脚本
data/story/                 正文固定题目、价格指数与模型参考输出
src/                        可运行的教学版研究代码
config/research_config.yaml 统一研究规格
data/README.md              真实数据需求、字段契约和缺口
templates/                  研究规格、研报复现、因子定义、报告与审计模板
outputs/                    自动生成的运行结果
```

本项目仅用于机器学习和量化研究方法教育，不构成投资建议、收益承诺、个股推荐或实盘操作指引。真实交易还需要可靠的数据供应、规则校验、容量评估、风险管理、执行和合规流程。
