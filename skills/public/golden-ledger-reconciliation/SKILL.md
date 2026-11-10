---
name: golden-ledger-reconciliation
description: NautilusTrader 纯观察回测与黄金账本核算规约（Backtest Agent 专用）。规定零合成盘口要求、T+1 撮合与 Decimal 精度三方对账。
---

# 纯观察微观回测与黄金账本核算规约

本规约定义了 Backtest Agent（回测专员）在运行 NautilusTrader 1.231.0 时的硬性规范：

## 核心规范
1. **纯观察 Bar 驱动（零合成盘口）**：
   - 彻底关闭 `synthetic_book`；
   - 严禁从日线/分钟线 Bar 伪造买一卖一挂单深度；
   - 以实际可观测的开盘价/收盘价执行 IOC 限价单，每根 Bar 共享不超过 $1\%$ 真实成交量预算。
2. **法定税费精准核算**：
   - 卖出方计提千分之一或万分之五印花税（依据历史法定日期）；
   - 双边过户费与券商佣金最低 5 元保底。
3. **GoldenLedger 独立黄金账本三方恒等对账**：
   - 原生 Nautilus 现金 $\equiv$ 参考账本现金（Decimal 精度）；
   - 原生持仓股数 $\equiv$ 参考账本持仓股数；
   - 现金差异与 NAV 差异必须恒等于 0.00；
   - 任何未解释分差（`unexplained != 0`）立即判定回测失败并终止。
