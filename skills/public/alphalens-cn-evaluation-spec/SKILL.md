---
name: alphalens-cn-evaluation-spec
description: 因子有效性实证评估规约（Factor Agent 专用）。规定基于 Alphalens-cn 0.4.8 的 Rank IC、Newey-West HAC 稳健统计与负向门禁机制。
---

# 因子有效性实证评估规约 (Alphalens-cn Spec)

本规约定义了 Factor Agent（因子专员）在开展因子检验时的统计与实证标准：

## 核心标准
1. **时钟对齐**：
   - 信号生效时钟为每日 18:00（Asia/Shanghai），仅使用盘后已完全确认的行情与因子值；
   - 入场时点为下一交易日开盘（`entry_lag=1`）。
2. **多周期 HAC 稳健检验**：
   - 计算 1D、5D、20D 远期收益的 Rank IC；
   - 必须采用 Newey-West 异方差与时序自相关稳健协方差估计量（HAC），滞后阶数严格与持有期匹配（1D lag=1, 5D lag=5, 20D lag=20）；
   - 检验公式与独立复算误差必须严格满足 $\le 10^{-8}$。
3. **负向门禁与不达标处置**：
   - 若因子在回测样本期内 IC 均值小于门槛或为负（如 20 日动量因子），必须真实标记为 `FACTOR_NOT_ADMITTED`；
   - 严禁通过观察结果反向调参或偷换方向。
