# 第 13 章｜Boosting 与 LightGBM

上一章把多棵树的预测平均。Boosting 的思路是接着修正已有预测的误差。

假设某个历史样本的排名标签为 0.8，当前预测是 0.5，两者相差 0.3。下一步尝试学习这类误差；若本次只加入修正量的十分之一，预测变成 `0.5 + 0.1×0.3 = 0.53`。这里的 0.1 就帮助理解学习率。

这是单个样本的平方误差直觉，实际一棵树会同时拟合很多样本。LightGBM 是实现这类逐步提升模型的工具。先理解每轮在改什么，再看参数清单。

## 1. 与随机森林的区别

随机森林的树可以并行训练，最后平均；Boosting 按顺序训练，每一棵新树重点修正前面模型的残差。因此它通常拟合能力更强，也更容易在噪声上继续“纠错”。

XGBoost 和 LightGBM 都属于梯度提升树。基础阶段不必背实现细节，要掌握参数对容量和学习速度的影响。

## 2. 参数分组

- 模型容量：`num_leaves`, `max_depth`, `min_child_samples`。
- 学习速度：`learning_rate`, `n_estimators`。
- 随机化：行采样、列采样及其种子。
- 正则化：L1/L2、最小增益等。

`learning_rate` 较小通常需要更多树；`num_leaves` 过大且叶子样本过少，容易记住局部噪声。

## 3. Early Stopping

正式实验应监控验证集，若若干轮没有改善就停止。测试集不能参与停止轮数选择。本项目已在每个滚动折中把 Validation 传给 LightGBM，并使用 `callbacks=[early_stopping(...)]` 得到 `best_iteration_`；随后用相同停止轮数在 Train+Validation 上重训，再预测 Test。

Early Stopping 解决的是“树继续增加是否还改善验证损失”，不自动保证 RankIC 最优。本项目同时记录停止轮数和验证期 RankIC。若损失下降但 RankIC 下降，应先明确研究目标，再决定评价指标，而不是挑对自己最有利的那个结果。

## 4. 调参纪律

先让默认模型超过 Ridge，再做小范围单变量实验。不要运行数百组参数后只报告最好结果。批量搜索增加了“多次尝试偶然获胜”的概率，需要额外的未触碰测试期验证。

## 练习

固定 `num_leaves=15`，比较 `learning_rate × n_estimators` 的三组等容量组合，例如 `(0.1, 40)`, `(0.04, 100)`, `(0.02, 200)`，记录训练时间和跨折稳定性。

## 5. Boosting 的一步直觉

设第一棵树给出了预测 `f_1(x)`，真实标签为 `y`，第二棵树不必从零开始预测 y，而是尝试拟合当前误差：

```text
残差 = y - f_1(x)
f_2(x) ≈ 残差
最终预测 = f_1(x) + learning_rate * f_2(x)
```

后续树继续修正剩余误差。`learning_rate` 越小，每棵树的影响越弱，通常需要更多树；树太深或叶子样本太少时，模型可能把随机波动当成残差规律。

## 6. Early Stopping 的完整流程

当前代码的流程可以简化为：

```python
candidate.fit(
    x_train,
    y_train,
    eval_set=[(x_validation, y_validation)],
    callbacks=[early_stopping(stopping_rounds=30, verbose=False)],
)
best_iteration = candidate.best_iteration_

final = LGBMRegressor(n_estimators=best_iteration, ...)
final.fit(x_train_validation, y_train_validation)
```

候选模型用 Validation 决定停止轮数；最终模型再用 Train+Validation 重训；Test 不参与停止。必须保存 `best_iteration` 和验证指标，否则别人无法知道最终树数量是预先规定的还是看了测试结果后手工调整的。

## 7. 损失函数与研究目标

LightGBM 默认回归损失常关注均方误差，但课程最终关心的是横截面排序 RankIC。损失下降不保证 RankIC 上升，原因包括：

- 少数极端收益主导平方误差；
- 模型改善了幅度预测，却没有改变股票排序；
- 不同交易日的标签尺度不同；
- 组合只使用 Top-N，排序尾部误差不重要。

因此每折同时记录验证损失、验证 RankIC 和最终测试 RankIC。若研究目标明确是排序，应进一步探索排序损失或分位数目标，但不能在本教程中把不同目标的结果混为一谈。

## 8. 与随机森林的比较实验

保持股票池、标签、滚动切分和成本不变，只比较模型：

| 模型 | 建树方式 | 主要风险 | 适合的第一步 |
|---|---|---|---|
| Random Forest | 独立树平均 | 树过深、方差较大 | 稳定非线性基线 |
| LightGBM | 顺序修正残差 | 过拟合和多次调参 | 小范围提升实验 |

如果 LightGBM 只在一个折或一个年份胜出，不应据此宣布复杂模型更好。先看跨折均值、正 IC 比例、压力成本和参数是否稳定。

练习答案框架：把三组学习率/树数写入实验表，记录每折停止轮数和 RankIC；若低学习率模型训练更慢但验证更稳定，可以保留为候选，否则选择更简单的规格。最终不能按测试期最高收益挑组合。
