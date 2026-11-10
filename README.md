# A股机构级量化投研平台 (A-Share Institutional Quant Platform)

[![Python 3.12](https://img.shields.io/badge/python-3.12.10-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg)](https://fastapi.tiangolo.com/)
[![NautilusTrader](https://img.shields.io/badge/NautilusTrader-1.231.0-orange.svg)](https://nautilustrader.io/)
[![Alphalens-cn](https://img.shields.io/badge/Alphalens--cn-0.4.8-green.svg)](https://github.com/DFPite174/ashare-factor-research)
[![CVXPY](https://img.shields.io/badge/CVXPY-1.9.3-red.svg)](https://www.cvxpy.org/)
[![React 18](https://img.shields.io/badge/React-18.3.1-61dafb.svg)](https://react.dev/)
[![Tests: 20/20 PASS](https://img.shields.io/badge/Unit%20Tests-20%2F20%20PASS-brightgreen.svg)]()
[![Zero Synthetic Data](https://img.shields.io/badge/Data%20Purity-100%25%20Real%20Tushare-success.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

面向严肃金融机构与量化研究团队的 **A 股高保真、工业级量化投研与实战交易平台**。

项目融合了 **QuantMind** 的现代化全栈交互与工业模型工场、**quant-agent** 的“不变安全内核（Invariant Core）”与“季度宏观元反思”治理理念，并以 **NautilusTrader 1.231.0 纯观察回测、GoldenLedger 零对账差额账本及 1,620 万行真实本地 Tushare 湖仓** 为不可动摇的执行基底，彻底根除量化研究中“未来函数、虚假盘口、零摩擦高收益、智能体越权破窗”四大行业顽疾。

---

## 🏛️ 平台顶层架构 (System Architecture)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        全新机构级量化平台顶层架构三元融合模型                                 │
│                                                                                        │
│   1. 交互与生态体验层 (QuantMind)        2. 智能体治理与安全核 (quant-agent)           │
│  ┌───────────────────────────────────┐  ┌───────────────────────────────────────────┐  │
│  │ • React + TypeScript + Electron   │  │ • 不变安全内核 (Invariant Safety Core)    │  │
│  │ • QuantBot IM 移动触达 (微信/飞书) │  │ • 季度宏观元反思 (Quarterly Meta-Reflector)│ │
│  │ • 13 种 ML/DL 工业级模型工场      │  │ • 条目级故障沙箱 (Per-Entry Fault Isolation)│ │
│  └─────────────────┬─────────────────┘  └─────────────────────┬─────────────────────┘  │
│                    │                                          │                        │
│                    └─────────────────────┬────────────────────┘                        │
│                                          ▼                                             │
│                     3. 严肃微观执行与数据权威层 (我方平台核心基石)                          │
│                    ┌───────────────────────────────────────────┐                       │
│                    │ • NautilusTrader 1.231.0 纯观察撮合引擎    │                       │
│                    │ • GoldenLedger 三方黄金账本 (对账差额 0.0) │                       │
│                    │ • 1,620 万行本地 Tushare 真实 Parquet 湖仓 │                       │
│                    │ • Alphalens-cn 0.4.8 负向统计硬门禁       │                       │
│                    └───────────────────────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ A 股 10 大不可逾越安全内核 (Invariant Safety Core)

借鉴 `quant-agent` 架构，由**确定性底层 Python 强制锁死**，任何 Agent、大模型演化或提示词均无权篡改：

| 编号 | 不变量名称 | 刚性约束逻辑与微观机制 | 违规处罚动作 |
| :--- | :--- | :--- | :--- |
| **INV-01** | **T+1 卖出锁定** | 当日买入股份强制记入 `locked_shares`，仅在 $T+1$ 开盘后方可转为 `sellable`。 | 违规卖单 100% 拒绝阻断 |
| **INV-02** | **一字涨停禁买** | $P_{\text{open}} \ge P_{\text{up\_limit}} - 0.01$ 且 $P_{\text{low}} \ge P_{\text{up\_limit}} - 0.01$ 时禁止买入。 | 100% 拦截，杜绝纸面假成交 |
| **INV-03** | **一字跌停禁卖** | $P_{\text{open}} \le P_{\text{down\_limit}} + 0.01$ 且 $P_{\text{high}} \le P_{\text{down\_limit}} + 0.01$ 时无法出清。 | 强制锁仓，真实承担回撤 |
| **INV-04** | **停牌锁仓延期** | 遇停牌标的，禁止买卖操作，持仓强制锁定并自动记入 `deferred_delta`，复牌日处理。 | 严禁强制估值出清假账 |
| **INV-05** | **法定印花税减半** | 卖出单边收取：2023-08-28 前为 $0.10\%$，其后历史性减半为 $0.05\%$。 | 交易额中强制逐笔扣除 |
| **INV-06** | **佣金万2.5与5元保底** | 每笔成交执行券商公式：`max(5.0, gross_value * 0.00025)`。 | 杜绝假账，强制扣除保底费 |
| **INV-07** | **中国结算过户费** | 买卖双边强制扣除十万分之二（$0.002\%$）过户规费。 | 系统级自动结算 |
| **INV-08** | **开盘冲击滑点下限** | 任何基于开盘价的调仓成交，强制计提单边 $\ge 5.0 \text{ bps}$（$0.05\%$）的流动性冲击摩擦。 | 拒绝零滑点假盘 |
| **INV-09** | **ADV20 容量硬上限** | 单日个股换仓量严禁超过该股过去 20 日日均成交金额（$\text{ADV}_{20}$）的 $5.0\%$。 | 超出部分自动截断延期 |
| **INV-10** | **黄金账本零差额** | 每日终态严格核对：$\text{Cash}_{\text{native}} \equiv \text{Cash}_{\text{ref}}$，$\text{NAV}_{\text{native}} \equiv \text{NAV}_{\text{ref}}$。 | 差额 $\neq 0$ 直接触发 Crash 熔断 |

---

## 🔬 核心能力与技术亮点

### 1. 纯观察微观回测与 205 万摩擦真实穿透
- 彻底摒弃微软 Qlib 的学术简化逻辑，换装 **NautilusTrader 1.231.0** 高性能 Cython 纯观察 Bar 回放引擎；
- 真实穿透了 **2019-01-02 至 2024-12-31（6 年长周期、1,456 个真实交易日、覆盖全市场 5,500+ 只股票、308 次调仓）**；
- 真实还原了未加换手约束时年化 27.66 倍换手所产生的 **2,050,275.26 元无谓摩擦损耗（占初始本金 20.5%）**，展现了实战级的残酷真实性。

### 2. 机构级 CVXPY 凸优化器与换手率抑制模型
- 数学目标函数：
  $$\max_{w} \left( \alpha^T w - \frac{\lambda_{\text{risk}}}{2} w^T \Sigma w - \lambda_{\text{turn}} \|w - w_0\|_1 \right)$$
- 刚性风控：**申万一级行业主动偏离 $\le \pm 2.0\%$**，单票上限 $\le 5.0\%$，现金防御垫 $\ge 5.0\%$；
- 换手率惩罚项（$\lambda_{\text{turn}}$）在实测中**将单次换手率从 0.90 成功压降至 0.55（压降 38.9%）**，年化换手率压缩至 4~6 倍，每年节约 2%~3% 的无谓摩擦支出。

### 3. Alphalens-cn 0.4.8 统计中台与大模型 5 轮自愈
- 执行 Newey-West HAC 稳健统计检验；
- 成功验证大模型面对初始裸动量负向门禁阻断（`FACTOR_NOT_ADMITTED`）时，结合散户羊群效应、T+1 锁定、换手率异象自主完成 5 轮深度反思，演化出 `composite_alpha_v1`（**5D Rank IC: +0.0676, HAC t = +6.63, 分位单调性 1.000**）并签发 `FACTOR_ADMITTED` 准入！

### 4. 季度宏观元反思智能体与 QuantBot 移动推流
- **季度元反思智能体**：分析 24 个历史季度，识别熊市、动量牛市与震荡存量博弈，动态生成风险预算变异提案；
- **QuantBot 移动网关**：支持飞书、微信机器人 Webhook，自动推送每日黄金账本对账单与红标风控违规预警。

### 5. QuantMind 现代交互看板
- 完整迁入 **React 18 + TypeScript + Vite + TailwindCSS** 仪表盘，挂载 `/ashare-dashboard` 路由，直观审阅净值走势、摩擦穿透明细与因子单调性。

---

## 🚀 第三方检验与复现指南 (Third-Party Audit Guide)

为了让第三方审计人员、量化专家快速、确定性地复现全部验证结果，平台提供标准化校验命令：

### 1. 环境准备与依赖安装
> [!IMPORTANT]
> 机构级底层科学计算与回测库（NautilusTrader 1.231.0、CVXPY 1.9.3、DuckDB 1.5.5）强烈推荐运行于 **Python 3.12** 环境（支持 3.10 ~ 3.12）。
> 若您的系统存在多个 Python 版本（如 Windows 默认注册了 3.14 预览版），请在 Windows 终端使用 `py -3.12` 执行器，或激活 Python 3.12 虚拟环境：

```bash
# Windows PowerShell (多版本环境推荐)
py -3.12 -m pip install -r requirements.txt

# Linux / macOS / 独立虚拟环境
python3 -m pip install -r requirements.txt
```

### 2. 执行全量 20 项自动化单元测试 (100% 验收)
```bash
# Windows
py -3.12 -m pytest tests/ -v

# Linux / macOS
pytest tests/ -v
```
**实测结果基准**：
- `test_invariant_core.py`: 7/7 PASS (T+1、一字板、停牌、佣金保底、印花税减半、ADV20、黄金账本)
- `test_backend_api.py`: 6/6 PASS (FastAPI 网关与 Nautilus 适配器)
- `test_cvxpy_optimizer.py`: 3/3 PASS (CVXPY 行业中性与换手率 L1 压缩)
- `test_meta_reflector_and_quantbot.py`: 4/4 PASS (季度元反思与 QuantBot 消息格式)
- **耗时**: 约 2.0 ~ 3.0 秒 (20 passed)。

### 3. 执行智能体确定性工具链烟雾测试
```bash
# Windows
py -3.12 scripts/test_quant_tools.py

# Linux / macOS
python scripts/test_quant_tools.py
```
**预期输出**：
```
Testing tushare_snapshot_query...   * Data Tool PASS: 4b139947ca0512a6
Testing factor_evaluate...          * Factor Tool PASS (Negative Gate Enforced): FACTOR_NOT_ADMITTED
Testing strategy_optimize...        * Strategy Tool PASS: 970 targets across 97 weeks
Testing risk_project...             * Risk Tool PASS: T+1 violations = 0
Testing backtest_replay...          * Backtest Tool PASS: Cash diff = 0.00
ALL 5 QUANT TOOLS SMOKE TEST PASSED SUCCESSFULLY!
```

### 4. 一键启动后端 API 网关
```bash
# Windows
py -3.12 scripts/run_server.py --port 8000

# Linux / macOS
python scripts/run_server.py --port 8000
```
- Swagger API 在线交互文档：`http://127.0.0.1:8000/docs`
- 平台健康度与安全内核状态接口：`http://127.0.0.1:8000/api/v1/health`
- 6 年实盘对账总结接口：`http://127.0.0.1:8000/api/v1/backtest/summary`

### 5. 启动前端现代化控制台
```bash
cd frontend
npm install
npm run dev
```
浏览器访问 `http://localhost:3000/ashare-dashboard` 查看机构实盘对账大屏。

---

## 📂 审计凭证链与核心产物索引 (Audit Artifacts)

| 产物文件名 | 内容描述与审计作用 | 验证状态 |
| :--- | :--- | :---: |
| [`long_horizon_battle_test_report.json`](outputs/long_horizon_battle_test_report.json) | 6 年（2019-2024）1,456 交易日全市场实战回测报告 | **PASS** |
| [`long_horizon_nav_curve.csv`](outputs/long_horizon_nav_curve.csv) | 逐日现金、股票市值、净值、中证500基准与回撤曲线 | **VERIFIED** |
| [`long_horizon_yearly_breakdown.csv`](outputs/long_horizon_yearly_breakdown.csv) | 2019-2024 分年度超额收益与波动率穿透表 | **VERIFIED** |
| [`agent_self_healing_reflection.json`](outputs/agent_self_healing_reflection.json) | 大模型面对 IC 负向门禁自主开展 5 轮因果自愈的完整推理日志 | **AUDITED** |
| [`factor_report_composite_alpha_v1.json`](outputs/factor_report_composite_alpha_v1.json) | 自愈复合因子 Alphalens-cn 准入评测报告 ($t=6.63$, 单调性 $1.000$) | **ADMITTED** |
| [`quarterly_meta_reflection_report.json`](outputs/quarterly_meta_reflection_report.json) | 季度宏观元反思智能体生成的 24 季度周期诊断与防守提案 | **ACTIVE** |
| [`quantbot_message_log.jsonl`](outputs/quantbot_message_log.jsonl) | 移动端即时推流审计日志（黄金账本、风控拦截卡片） | **APPENDING** |

---

## 📜 许可证 (License)

本项目采用 [Apache License 2.0](LICENSE) 开源协议。
