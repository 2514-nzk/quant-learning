# A 股量化研究入门：从传统因子到机器学习选股

这是一套面向初学者的本地自学教材，已将《A股量化研究基础课程目录.pdf》的传统多因子研究内容融入原有机器学习教程。先学习 A 股规则、研究假设、研报复现、因子算子、价值/质量/动量与单因子检验，再学习多因子组合和机器学习。

从 [教材目录](教程/README.md) 开始；PDF 十模块的落点见 [课程融合对照](教程/附录A_课程融合与来源对照.md)。传统阶段有可直接运行的 pandas 小例子和四股票合成练习，月度 Top-50 案例作为注明数据与实现要求的进阶实训。**下方现有示例代码仍使用以下独立的 5 日研究规格：**

> T 日收盘后，用截至决策时点可获得的信息，预测 T+1 开盘至 T+5 收盘的横截面收益排名，把预测转成 Top-N 组合，并用滚动样本外方式评价。

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

### 有编程和股票经验的学习入口

先学习 [00d 量化 Python 实战](教程/00d_量化Python实战.md) 与 [00e 量化数学与统计](教程/00e_量化数学与统计.md)。重点是行情面板、日期与索引对齐、PIT、统计评价及结果的不确定性；00a 作为语法参考，00c 按研究口径查阅。

```powershell
python examples/quant_python_workshop.py
python examples/quant_math_workshop.py
```

两份脚本使用内置虚构数据，输出手算对照与边界核对，不需要外部数据源。

### 初级主线：先完成传统因子研究
1. 完成 00d、00e 的量化 Python 与数学练习，阅读 00 学习路线；00a、00c 按需查阅。
2. 按 `01 → 01a → 02 → 04 → 03 → 03a → 03b → 08a → 09 → 09a` 学习；时间切分提前掌握，不要求先学机器学习。
3. 完成研报复现卡、三张因子定义卡、单因子报告、三因子手算与稳健性审计。
4. 对照第 09a 章区分课堂练习与完整真实月度项目的实现要求。

### 机器学习扩展
1. 补充 00b 机器学习基础，回看 01–03 的 5 日研究规格。
2. 按 04–11 章阅读；第 11 章提供机器学习流程的手算与实验操作。
3. 运行 `python -m src.run_demo`，对照代码阅读 `src/`。
4. 修改 `config/research_config.yaml` 中的一个参数，记录变化到 `templates/experiment_log.csv`。
5. 最后再接入真实数据，不要一开始就用真实回测结果调参。

**遇到困难时：** 如果在学习过程中遇到 pandas 操作、机器学习概念或金融术语不理解，随时查阅 [`教程/README.md`](教程/README.md) 中的前置知识章节。

## 目录

```text
教程/                     传统因子与机器学习两阶段讲义、练习和规则附录
examples/                 量化 Python 与数学统计的独立教学脚本
src/                      可运行的教学版研究代码
config/research_config.yaml 统一研究规格
data/README.md            真实数据需求、字段契约和缺口
templates/                研究规格、研报复现、因子定义、研究报告与审计模板
outputs/                  运行结果（自动生成）
```

## 重要边界

本项目仅用于机器学习和量化研究方法教育，不构成投资建议、收益承诺、个股推荐或实盘操作指引。真实交易还需要可靠的数据供应、交易规则、容量评估、风控、执行和合规流程。
