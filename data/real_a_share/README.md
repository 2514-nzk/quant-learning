# AKShare 真实 A 股历史 K 线教学快照

**这是真实历史市场价格，不是模拟生成的数据；但它也不是一个完整可回测的研究数据集。**

2026-11-11 固定的主课程样本包含 **2024-01-02 至 2024-06-28** 的历史日线，每只 117 行：贵州茅台（600519）、寒武纪（688256）、宁德时代（300750）、比亚迪（002594）。另外保存了平安银行（000001）的独立历史日线；它不属于本书四股教学组合。

接口优先级：`stock_zh_a_hist`（东方财富）→ `stock_zh_a_daily`（新浪，备用）。本次东方财富接口返回异常，**三只均通过 AKShare 新浪历史行情接口采集**。每只数据实际使用的接口在 [manifest.json](manifest.json) 中有单独记录；再次采集时不保证源会自动保持相同。

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
python -m pip install akshare
python scripts/collect_real_a_share.py
python -m unittest discover -s tests -p "test_real_a_share.py" -v
python examples/real_kline_lab.py --symbol 000001
~~~

由于公共数据源可能限流、不可用、更新数据或调整接口，重新运行可能导致数值变化；应保留已有数据快照的采集时间与 SHA256，不能在数据被覆盖后直接声称完全复现。自动采集记录在 GitHub Actions 的 `Collect AKShare real A-share teaching charts` 工作流；手动刷新后要重新部署阅读网站才能展示新图。

**边界：** 没有按历史时点建立完整股票池，也没有分红复权、财务 PIT、除权事件核对、停牌/涨跌停成交限制与费用账本。不能对这三只股票的纸面历史形态计算策略业绩，再宣称获得真实市场的样本外 Alpha。完整实证要求见 [数据需求与缺口](../README.md)。
## 第二卷历史股票池覆盖审计

运行 `python examples/advanced_universe_coverage_lab.py --real-teaching --json` 可得到四股真实 CSV 的 SHA、各自日期集合、共同**已观察日期**和来源缺口。**这不是完整 A 股股票池或官方交易日历**；没有权威分母时报告中的 `full_market_coverage_percent` 必须为 `null`。详见 [第二卷附录 C](../../advanced/volume-2/HISTORICAL_UNIVERSE_SOURCE_AUDIT.md)。
