---
name: research-workflow-spec
description: 量化投研全生命周期标准规约（Lead Agent 专用）。规定假说定义、分阶段委派流程、负向门禁审计与研发预算控制。
---

# 量化投研全生命周期标准规约 (Research Workflow Spec)

本规约定义了 Lead Agent（量化投研主控官）在调度各专业 Agent 时的行为准则与不可逾越的边界。

## 核心流程
1. **假说定义**：所有研究任务必须从具有明确经济逻辑的假说出发，明确预期方向（`positive` 或 `negative`）与验证窗口；
2. **有序分派**：
   - 委派 `data-engineer` 校验并提供数据快照 ID；
   - 委派 `factor-analyst` 计算因子并执行 Alphalens-cn 0.4.8 有效性实证；
   - 若因子实证未达标（如 `FACTOR_NOT_ADMITTED`），**立即阻断后续实盘报单生成**，并将失败原因记录至 DeerMem 记忆库；
   - 若通过，委派 `strategy-quant` 与 `risk-controller` 形成风控裁决订单；
   - 委派 `backtest-engine` 进行纯观察 Bar 执行与黄金账本核算；
3. **人类最终准入裁决权**：
   - Lead Agent 仅负责研发与回测自动化，**无权单方面签发实盘准入（Admit）**；
   - 最终准入必须提交给人类独立复核人进行独立样本复核与签名。
