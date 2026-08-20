# 量化机器学习基础：从数据到选股回测

这是一套根据《量化机器学习基础课程大纲》整理的本地自学教程，面向“会 Python、懂一点计算机、刚开始学量化”的学习者。课程主线固定为：

> 用 T 日收盘前可获得的信息，预测未来 5 个交易日的横截面相对收益，把预测转成 Top-N 组合，并用滚动样本外方式评价。

本仓库先用**可复现的合成股票面板数据**跑通完整闭环。合成数据不是投资数据，也不能证明任何策略有效；它的作用是让你先掌握时点、标签、切分、训练、预测和回测之间的连接。真实 A 股数据的最低字段和缺口见 [`data/README.md`](data/README.md)。

## 快速开始

```powershell
cd C:\Users\25148\Desktop\量化入门学习
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

教学回测使用与标签一致的非重叠 5 日持有期，并同时报告等权股票池基准和主动收益。它仍是简化回测，不含五组重叠持仓、逐笔成交和完整风格归因。

你已有 `D:/duckdb_data`，因此还可以直接运行只读真实数据示例：

```powershell
python -m src.run_duckdb_demo
```

它读取 `D:/duckdb_data/xc_tushare_data.snapshots/current.json` 指向的快照，不会写入或锁定主数据库。真实结果位于 `outputs/duckdb_demo/<run_id>/`，最近一次编号见同目录的 `latest.txt`。

## 学习顺序

### 零基础学习者
1. 先学习 **前置知识章节**（教程目录中的 00a、00b、00c），补充 Python 数据分析、机器学习和金融市场基础。
2. 再按下面的"有基础学习者"路径学习。

### 有基础学习者
1. 先读 [`教程/00_学习路线.md`](教程/00_学习路线.md)，理解研究对象和时间轴。
2. 按 01 到 11 章阅读；第 11 章提供贯穿全流程的手算案例和实验操作。
3. 运行 `python -m src.run_demo`，对照代码阅读 `src/`。
4. 修改 `config/research_config.yaml` 中的一个参数，记录变化到 `templates/experiment_log.csv`。
5. 最后再接入真实数据，不要一开始就用真实回测结果调参。

**遇到困难时：** 如果在学习过程中遇到 pandas 操作、机器学习概念或金融术语不理解，随时查阅 [`教程/README.md`](教程/README.md) 中的前置知识章节。

## 目录

```text
教程/                     11 个模块的中文讲义与练习
src/                      可运行的教学版研究代码
config/research_config.yaml 统一研究规格
data/README.md            真实数据需求、字段契约和缺口
templates/                研究问题、实验记录、泄漏审计模板
outputs/                  运行结果（自动生成）
```

## 重要边界

本项目仅用于机器学习和量化研究方法教育，不构成投资建议、收益承诺、个股推荐或实盘操作指引。真实交易还需要可靠的数据供应、交易规则、容量评估、风控、执行和合规流程。
