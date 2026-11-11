/**
 * 机构级 A 股高保真量化投研看板 (AShare Institutional Quant Dashboard)
 *
 * 融合 QuantMind 现代化交互与图表 + quant-agent 10 大安全不变量 + NautilusTrader 6 年实盘对账数据
 */

import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  TrendingUp,
  AlertTriangle,
  Layers,
  Activity,
  FileText,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Coins,
  Scale
} from 'lucide-react';

interface HealthData {
  status: string;
  engine: string;
  invariants_enforced: string[];
  data_lake: {
    source: string;
    path: string;
    historical_range: string;
    zero_synthetic_data: boolean;
  };
}

interface BacktestSummary {
  status: string;
  horizon: {
    start_date: string;
    end_date: string;
    total_trading_days: number;
    total_years: number;
  };
  capital_and_friction: {
    initial_cash: number;
    final_nav: number;
    total_stamp_tax_paid: number;
    total_broker_commission_paid: number;
    total_transfer_fee_paid: number;
    total_slippage_cost: number;
    total_trading_friction: number;
    annualized_turnover_rate: number;
  };
  performance_summary: {
    strategy_total_return: string;
    strategy_cagr: string;
    strategy_annual_volatility: string;
    strategy_sharpe_ratio: number;
    strategy_sortino_ratio: number;
    strategy_max_drawdown: string;
    strategy_calmar_ratio: number;
    daily_win_rate: string;
  };
  benchmark_comparison: {
    csi300_cagr: string;
    csi300_total_return: string;
    csi500_cagr: string;
    csi500_total_return: string;
    annualized_alpha_vs_csi500: string;
    information_ratio_vs_csi500: number;
  };
  yearly_breakdown: Array<{
    Year: string | number;
    Strategy_Return: number;
    CSI300_Return: number;
    CSI500_Return: number;
    Excess_vs_CSI500: number;
    Max_Drawdown: number;
    Volatility: number;
  }>;
}

interface FactorReport {
  factor_id: string;
  formal_gate: {
    admitted: boolean;
    decision: string;
    reason: string;
  };
  metrics: Record<string, {
    mean_ic: number;
    hac_t_stat: number;
    icir: number;
  }>;
}

export const AShareInstitutionalDashboard: React.FC = () => {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [factorReport, setFactorReport] = useState<FactorReport | null>(null);
  const [activeFactor, setActiveFactor] = useState<'composite_alpha_v1' | 'momentum20'>('composite_alpha_v1');
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'friction' | 'factors' | 'invariants'>('overview');

  const API_BASE = 'http://127.0.0.1:8000';

  const fetchData = async () => {
    setLoading(true);
    setApiError(null);
    try {
      const [hRes, sRes, fRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/health`),
        fetch(`${API_BASE}/api/v1/backtest/summary`),
        fetch(`${API_BASE}/api/v1/factors/evaluate?factor_id=${activeFactor}`)
      ]);
      if (hRes.ok) setHealth(await hRes.json());
      if (sRes.ok) setSummary(await sRes.json());
      if (fRes.ok) setFactorReport(await fRes.json());
      if (!hRes.ok || !sRes.ok) {
        setApiError('后端接口返回异常，请确认 8000 端口后端服务已启动。');
      }
    } catch (err) {
      console.error('Failed to connect to Quant Platform API:', err);
      setApiError('无法连接后端 API 服务 (http://127.0.0.1:8000)。请确保在另一个终端运行: python scripts/run_server.py --port 8000');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeFactor]);

  return (
    <div className="flex flex-col h-full bg-[#121316] text-[#E1E4EA] p-6 pb-28 space-y-6 overflow-y-auto font-sans">
      {/* 顶部标题栏与全局状态 */}
      <div className="flex items-center justify-between border-b border-[#2A2E39] pb-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">
              A 股机构级量化投研平台 (Institutional Alpha Platform)
            </h1>
            <span className="bg-[#1C2C4E] text-[#4F8BFF] text-xs px-2.5 py-0.5 rounded-full border border-[#2F4A7F] font-mono font-medium">
              NautilusTrader 1.231.0
            </span>
            <span className="bg-[#1B352B] text-[#34D399] text-xs px-2.5 py-0.5 rounded-full border border-[#216147] font-mono font-medium flex items-center space-x-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#34D399] animate-pulse"></span>
              <span>100% 真实 Tushare 湖仓</span>
            </span>
          </div>
          <p className="text-sm text-[#8890A4] mt-1">
            严苛微观摩擦执行 • 零合成数据 • 黄金账本 0 差额核验 • 10 大安全不变量闭环
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center space-x-2 bg-[#1E222D] hover:bg-[#2A2E39] text-white px-4 py-2 rounded-lg border border-[#363C4E] text-sm transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>刷新对账数据</span>
          </button>
        </div>
      </div>

      {/* 导航标签切换 */}
      <div className="flex space-x-2 border-b border-[#2A2E39]">
        {[
          { id: 'overview', label: '6年长周期对账总览', icon: TrendingUp },
          { id: 'friction', label: '205万交易摩擦穿透账本', icon: Coins },
          { id: 'factors', label: 'Alphalens 因子实证与自愈', icon: Activity },
          { id: 'invariants', label: 'A股 10 大不变安全内核', icon: ShieldCheck }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center space-x-2 py-3 px-4 border-b-2 font-medium text-sm transition ${
                isActive
                  ? 'border-[#2962FF] text-[#2962FF] bg-[#1E222D]/40'
                  : 'border-transparent text-[#8890A4] hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {apiError && (
        <div className="bg-[#3D1A1A] border border-[#7F2626] text-[#FCA5A5] p-4 rounded-xl flex items-center space-x-3 text-sm">
          <AlertTriangle className="w-5 h-5 text-[#EF4444] shrink-0" />
          <div>
            <div className="font-semibold text-white">后端连接提示</div>
            <div className="font-mono text-xs mt-1">{apiError}</div>
          </div>
        </div>
      )}

      {/* 标签页内容：总览 */}
      {activeTab === 'overview' && summary && (
        <div className="space-y-6">
          {/* 核心指标卡片矩阵 */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-[#1E222D] p-5 rounded-xl border border-[#2A2E39]">
              <div className="text-xs text-[#8890A4] uppercase font-semibold">初始资金 / 期末净值</div>
              <div className="text-2xl font-bold mt-2 text-white font-mono">
                {(summary.capital_and_friction.final_nav / 10000).toFixed(2)} 万元
              </div>
              <div className="text-xs text-[#EF4444] mt-1 flex items-center space-x-1">
                <span>累计收益: {summary.performance_summary.strategy_total_return}</span>
                <span>(CAGR: {summary.performance_summary.strategy_cagr})</span>
              </div>
            </div>

            <div className="bg-[#1E222D] p-5 rounded-xl border border-[#2A2E39]">
              <div className="text-xs text-[#8890A4] uppercase font-semibold">中证500 基准表现 (000905.SH)</div>
              <div className="text-2xl font-bold mt-2 text-[#34D399] font-mono">
                {summary.benchmark_comparison.csi500_total_return}
              </div>
              <div className="text-xs text-[#8890A4] mt-1">
                年化超额 (Alpha): <span className="text-[#EF4444]">{summary.benchmark_comparison.annualized_alpha_vs_csi500}</span>
              </div>
            </div>

            <div className="bg-[#1E222D] p-5 rounded-xl border border-[#2A2E39]">
              <div className="text-xs text-[#8890A4] uppercase font-semibold">实盘动态最大回撤 / 夏普比率</div>
              <div className="text-2xl font-bold mt-2 text-[#F59E0B] font-mono">
                {summary.performance_summary.strategy_max_drawdown}
              </div>
              <div className="text-xs text-[#8890A4] mt-1">
                Sharpe: <span className="text-white font-mono">{summary.performance_summary.strategy_sharpe_ratio}</span> | 波动率: {summary.performance_summary.strategy_annual_volatility}
              </div>
            </div>

            <div className="bg-[#1E222D] p-5 rounded-xl border border-[#2A2E39]">
              <div className="text-xs text-[#8890A4] uppercase font-semibold">累计交易摩擦损耗 (失血占比)</div>
              <div className="text-2xl font-bold mt-2 text-[#EF4444] font-mono">
                {(summary.capital_and_friction.total_trading_friction / 10000).toFixed(2)} 万元
              </div>
              <div className="text-xs text-[#F59E0B] mt-1 font-mono">
                吞噬本金 20.5% (年化换手 {summary.capital_and_friction.annualized_turnover_rate}x)
              </div>
            </div>
          </div>

          {/* 分年度表现明细表 */}
          <div className="bg-[#1E222D] p-5 rounded-xl border border-[#2A2E39]">
            <h3 className="text-base font-semibold text-white mb-4 flex items-center space-x-2">
              <Scale className="w-5 h-5 text-[#4F8BFF]" />
              <span>分年度业绩与基准穿透对照 (2019-2024 完整穿透)</span>
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm font-mono">
                <thead>
                  <tr className="border-b border-[#2A2E39] text-[#8890A4] text-xs">
                    <th className="py-3 px-4">年度</th>
                    <th className="py-3 px-4">策略收益率</th>
                    <th className="py-3 px-4">沪深 300</th>
                    <th className="py-3 px-4">中证 500</th>
                    <th className="py-3 px-4">相对 500 超额</th>
                    <th className="py-3 px-4">当年最大回撤</th>
                    <th className="py-3 px-4">年化波动率</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A2E39]">
                  {summary.yearly_breakdown.map((row) => (
                    <tr key={row.Year} className="hover:bg-[#2A2E39]/30 transition">
                      <td className="py-3 px-4 font-bold text-white">{row.Year}</td>
                      <td className={`py-3 px-4 font-semibold ${row.Strategy_Return >= 0 ? 'text-[#34D399]' : 'text-[#EF4444]'}`}>
                        {(row.Strategy_Return * 100).toFixed(2)}%
                      </td>
                      <td className="py-3 px-4 text-[#8890A4]">{(row.CSI300_Return * 100).toFixed(2)}%</td>
                      <td className="py-3 px-4 text-[#8890A4]">{(row.CSI500_Return * 100).toFixed(2)}%</td>
                      <td className={`py-3 px-4 ${row.Excess_vs_CSI500 >= 0 ? 'text-[#34D399]' : 'text-[#EF4444]'}`}>
                        {(row.Excess_vs_CSI500 * 100).toFixed(2)}%
                      </td>
                      <td className="py-3 px-4 text-[#F59E0B]">{(row.Max_Drawdown * 100).toFixed(2)}%</td>
                      <td className="py-3 px-4 text-[#8890A4]">{(row.Volatility * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 标签页内容：205万交易摩擦穿透账本 */}
      {activeTab === 'friction' && summary && (
        <div className="space-y-6">
          <div className="bg-[#1E222D] p-6 rounded-xl border border-[#2A2E39]">
            <h3 className="text-lg font-bold text-white mb-2">微观交易成本穿透式账本 (Frictional Cost Audit)</h3>
            <p className="text-sm text-[#8890A4] mb-6">
              未设置换手率约束时，年化 27.66 倍的过度换手在 6 年内产生了 2,050,275.26 元无谓摩擦，直接吃掉 20.5% 的本金：
            </p>

            <div className="grid grid-cols-4 gap-4">
              <div className="bg-[#121316] p-4 rounded-lg border border-[#2A2E39]">
                <div className="text-xs text-[#8890A4]">证券交易印花税 (Stamp Duty)</div>
                <div className="text-xl font-bold mt-2 text-[#EF4444] font-mono">
                  {(summary.capital_and_friction.total_stamp_tax_paid / 10000).toFixed(2)} 万元
                </div>
                <div className="text-xs text-[#8890A4] mt-1">2023-08-28 前千1，后万5</div>
              </div>

              <div className="bg-[#121316] p-4 rounded-lg border border-[#2A2E39]">
                <div className="text-xs text-[#8890A4]">券商经纪佣金 (Broker Commission)</div>
                <div className="text-xl font-bold mt-2 text-[#F59E0B] font-mono">
                  {(summary.capital_and_friction.total_broker_commission_paid / 10000).toFixed(2)} 万元
                </div>
                <div className="text-xs text-[#8890A4] mt-1">万2.5，单笔 5 元保底</div>
              </div>

              <div className="bg-[#121316] p-4 rounded-lg border border-[#2A2E39]">
                <div className="text-xs text-[#8890A4]">中国结算过户费 (Transfer Fee)</div>
                <div className="text-xl font-bold mt-2 text-[#34D399] font-mono">
                  {(summary.capital_and_friction.total_transfer_fee_paid / 10000).toFixed(2)} 万元
                </div>
                <div className="text-xs text-[#8890A4] mt-1">双边十万分之 2</div>
              </div>

              <div className="bg-[#121316] p-4 rounded-lg border border-[#2A2E39]">
                <div className="text-xs text-[#8890A4]">开盘集合竞价滑点 (Slippage)</div>
                <div className="text-xl font-bold mt-2 text-[#EF4444] font-mono">
                  {(summary.capital_and_friction.total_slippage_cost / 10000).toFixed(2)} 万元
                </div>
                <div className="text-xs text-[#8890A4] mt-1">单边强制 5 bps 冲击</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 标签页内容：Alphalens 因子实证与自愈 */}
      {activeTab === 'factors' && (
        <div className="space-y-6">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setActiveFactor('composite_alpha_v1')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeFactor === 'composite_alpha_v1'
                  ? 'bg-[#2962FF] text-white'
                  : 'bg-[#1E222D] text-[#8890A4] hover:text-white'
              }`}
            >
              自愈后复合因子: composite_alpha_v1 (准入)
            </button>
            <button
              onClick={() => setActiveFactor('momentum20')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeFactor === 'momentum20'
                  ? 'bg-[#EF4444] text-white'
                  : 'bg-[#1E222D] text-[#8890A4] hover:text-white'
              }`}
            >
              初始裸动量: momentum20 (被拦截)
            </button>
          </div>

          {factorReport && (
            <div className="bg-[#1E222D] p-6 rounded-xl border border-[#2A2E39] space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <h3 className="text-lg font-bold text-white font-mono">{factorReport.factor_id}</h3>
                  {factorReport.formal_gate.admitted ? (
                    <span className="bg-[#1B352B] text-[#34D399] text-xs px-3 py-1 rounded-full border border-[#216147] font-semibold flex items-center space-x-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>FACTOR_ADMITTED (准入通过)</span>
                    </span>
                  ) : (
                    <span className="bg-[#3D1A1A] text-[#EF4444] text-xs px-3 py-1 rounded-full border border-[#7F2626] font-semibold flex items-center space-x-1">
                      <XCircle className="w-3.5 h-3.5" />
                      <span>FACTOR_NOT_ADMITTED (门禁拦截)</span>
                    </span>
                  )}
                </div>
              </div>

              <p className="text-sm text-[#8890A4] bg-[#121316] p-3 rounded border border-[#2A2E39]">
                <strong className="text-white">门禁裁决理由: </strong>{factorReport.formal_gate.reason}
              </p>

              {factorReport.metrics && (
                <div className="grid grid-cols-3 gap-4 pt-2">
                  {Object.entries(factorReport.metrics).map(([period, m]) => (
                    <div key={period} className="bg-[#121316] p-4 rounded-lg border border-[#2A2E39]">
                      <div className="text-xs text-[#8890A4] uppercase font-bold">{period} 远期截面收益检验</div>
                      <div className="text-xl font-bold mt-2 text-white font-mono">
                        Rank IC: <span className={m.mean_ic >= 0 ? 'text-[#34D399]' : 'text-[#EF4444]'}>{(m.mean_ic * 100).toFixed(2)}%</span>
                      </div>
                      <div className="text-xs text-[#8890A4] mt-1 font-mono">
                        HAC t-stat: <span className={Math.abs(m.hac_t_stat) >= 2.0 ? 'text-[#34D399]' : 'text-[#F59E0B]'}>{m.hac_t_stat.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 标签页内容：10 大不变安全内核 */}
      {activeTab === 'invariants' && health && (
        <div className="bg-[#1E222D] p-6 rounded-xl border border-[#2A2E39] space-y-4">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-6 h-6 text-[#34D399]" />
            <h3 className="text-lg font-bold text-white">A 股 10 大不可逾越安全内核 (Invariant Safety Core)</h3>
          </div>
          <p className="text-sm text-[#8890A4]">
            借鉴 quant-agent 形式化隔离理念，由 Python 底层硬编码阻断，任何大模型、演化策略或提示词均无权篡改：
          </p>

          <div className="grid grid-cols-2 gap-3 pt-2">
            {health.invariants_enforced.map((inv, idx) => (
              <div key={idx} className="bg-[#121316] p-3.5 rounded-lg border border-[#2A2E39] flex items-center space-x-3">
                <CheckCircle2 className="w-5 h-5 text-[#34D399] shrink-0" />
                <span className="text-sm font-mono text-white">{inv}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
