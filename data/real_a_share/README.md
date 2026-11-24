# AKShare 真实 A 股历史 K 线教学快照

**这是真实历史市场价格，不是模拟生成的数据；但它也不是一个完整可回测的研究数据集。**

2026-11-11 固定的主课程样本包含 **2024-01-02 至 2024-06-28** 的历史日线，每只 117 行：贵州茅台（600519）、寒武纪（688256）、宁德时代（300750）、比亚迪（002594）。另外保存了平安银行（000001）的独立历史日线；它不属于本书四股教学组合。

这份冻结快照于 2026-11-11 使用 AKShare 1.20.37 采集；[manifest.json](manifest.json) 记录四只股票均来自当时的新浪旧接口名 `stock_zh_a_daily`。AKShare 后续统一并更名了接口：当前刷新程序改用 `stock_zh_a_hist_em`（东方财富）和 `stock_zh_a_hist_sina`（新浪备用）。因此，历史 manifest 保留旧接口名是来源记录，不是当前脚本仍在调用旧接口。

## 字段

| CSV 字段 | 含义 | 单位与说明 |
|---|---|---|
| trade_date | 交易日期 | YYYY-MM-DD，上海/深圳本地市场日历 |
| symbol, name | 股票代码、名称 | 名称为脚本内固定的教学标签 |
| open, high, low, close | 当日开高低收 | 元/股，**不复权** |
| volume_lots | 成交量 | 手；新浪数据原始单位为股，转换为每 100 股一手 |
| amount_yuan | 成交额 | 元；源端缺失时留空，不用 0 代替 |
| turnover_pct | 换手率 | **百分数**；新浪原始小数×100，东方财富已按百分数返回 |

每只主课程 CSV 对应一张 SVG 图：`reader/assets/real-a-share/<代码>.svg`。图片最后显示 55 根日 K 线及 MA5、MA20 和成交量；CSV 保存完整窗口。图是对**真实来源数据**的本地绘制，未对价格或涨跌方向进行人工修饰。

## 复现（需要网络）

在项目根目录运行：

~~~powershell
python -m pip install --upgrade akshare
python scripts/collect_real_a_share.py
python -m unittest discover -s tests -p "test_real_a_share.py" -v
python examples/real_kline_lab.py --symbol 000001
~~~

由于公共数据源可能限流、不可用、更新数据或调整接口，重新运行可能导致数值变化；应保留已有数据快照的采集时间与 SHA256，不能在数据被覆盖后直接声称完全复现。自动采集记录在 GitHub Actions 的 `Collect AKShare real A-share teaching charts` 工作流；手动刷新后要重新部署阅读网站才能展示新图。

**边界：** 没有按历史时点建立完整股票池，也没有分红复权、财务 PIT、除权事件核对、停牌/涨跌停成交限制与费用账本。不能对这四只股票的纸面历史形态计算策略业绩，再宣称获得真实市场的样本外 Alpha。完整实证要求见 [数据需求与缺口](../README.md)。
## 教材数据版本

当前四股固定数据属于 [教材专用真实价格包](../teaching/README.md)，用来复算有限样本的价格与因子算术。全市场 PIT、成交与市场有效性不在此数据包的证明范围。更大真实行情若重新采集，需要新数据版本和来源许可审核。


## 扩展真实日线（本地可选，不覆盖上述快照）

批量脚本使用当前 AKShare 命名：stock_zh_a_hist_em（东方财富）和 stock_zh_a_hist_sina（新浪备用）。AKShare 在 1.20.41–1.20.54 期间统一接口命名，旧 stock_zh_a_hist 已改名为 stock_zh_a_hist_em；不要照搬旧教程里的旧接口名。参见 [AKShare 当前接口说明](https://github.com/akfamily/akshare#使用)。

批量包保存 raw/ 与 qfq/ 两份独立原始响应。qfq 是本次抓取时点的前复权快照，历史值可能随后续公司行为而重述，不等于 PIT；原始数据保留供应商字段，不强行拼成统一列。脚本会记录源接口、成交量/换手率单位、失败和哈希。默认只保存到本地，不自动把数百只股票行情提交到公开仓库；是否可再分发需另行核查。

使用 [批量日线采集脚本](../../scripts/collect_research_daily.py)，详见[数据附录](../../advanced/volume-2/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md)。采集文件保留来源、范围、失败与 SHA-256；下载成功不代表动态 PIT 股票池成立。
