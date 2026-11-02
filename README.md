# A 股量化研究入门：从问题到样本外证据

这是一本沿研究流程编排的自学教材：从可检验的问题和数据时点开始，经过因子评价、组合构建和模型比较，最后完成可复核的研究。完整的五编、十六章顺序见[教材目录](教程/README.md)，也可以直接打开[在线阅读器](https://2514-nzk.github.io/quant-learning/)。

教材保留了两种互相补充的练习案例：可运行的五日模型研究，以及从手算和项目规格出发的月度三因子研究。它们的数据、频率和实现范围不同，不能直接比较回测收益。来源课程的模块映射见[课程融合与来源对照](教程/附录A_课程融合与来源对照.md)。

## 运行五日模型案例

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

教学回测使用与标签一致的非重叠 5 日持有期，并同时报告等权股票池基准和主动收益。它仍是简化回测，不含五组重叠持仓、逐笔成交和完整风格归因。合成数据不是投资数据，也不能证明任何策略有效；真实 A 股数据的最低字段和缺口见 [`data/README.md`](data/README.md)。

如果本地已有 `D:/duckdb_data`，还可以运行只读真实数据示例：

```powershell
python -m src.run_duckdb_demo
```

它读取 `D:/duckdb_data/xc_tushare_data.snapshots/current.json` 指向的快照，不会写入或锁定主数据库。真实结果位于 `outputs/duckdb_demo/<run_id>/`，最近一次编号见同目录的 `latest.txt`。

## 项目结构

```text
教程/                       教材正文、参考资料和规则附录
examples/                   Python 与数学统计练习脚本
src/                        可运行的教学版研究代码
config/research_config.yaml 统一研究规格
data/README.md              真实数据需求、字段契约和缺口
templates/                  研究规格、研报复现、因子定义、报告与审计模板
outputs/                    自动生成的运行结果
```

本项目仅用于机器学习和量化研究方法教育，不构成投资建议、收益承诺、个股推荐或实盘操作指引。真实交易还需要可靠的数据供应、规则校验、容量评估、风险管理、执行和合规流程。
