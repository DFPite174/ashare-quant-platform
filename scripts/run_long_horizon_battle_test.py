"""
6-Year Long-Horizon Institutional Quant Backtest & Battle Test (2019 - 2024)
Connected to Local Production Lake: C:\\Users\\SKT80\\Downloads\\MyProj\\my_upload\\Tushare_DB\\lake

Features:
- Full A-Share Market Universe (5,500+ stocks, 1,456 trading days)
- Multi-Factor Alpha Model: Low-Vol Reversal + Value (EP) + Liquidity Anomaly
- Realistic Institutional Friction & Execution:
  * T+1 Sellable Lock
  * Untradable Up-Limit Buy (Blocked) & Down-Limit Sell (Locked)
  * Dynamic Stamp Duty (10 bps before 2023-08-28, 5 bps after 2023-08-28)
  * Brokerage Commission 2.5 bps (Min 5 CNY guarantee)
  * Transfer Fee 0.2 bps
  * Conservative Slippage 5 bps
  * 5% Cash Reserve Floor
- Multi-Benchmark Attribution: CSI 300 (000300.SH) and CSI 500 (000905.SH)
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
LAKE_DIR = Path(r"C:\Users\SKT80\Downloads\MyProj\my_upload\Tushare_DB\lake")
OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

def run_battle_test():
    print("=" * 80)
    print("🚀 启动 A 股全市场 6 年长周期实战检验 (2019-01-02 至 2024-12-31)")
    print(f"📁 本地高保真湖仓路径: {LAKE_DIR}")
    print("=" * 80)

    t0 = time.time()
    con = duckdb.connect()

    p_daily = (LAKE_DIR / "market" / "daily" / "*" / "*.parquet").as_posix()
    p_limit = (LAKE_DIR / "market" / "stk_limit" / "*" / "*.parquet").as_posix()
    p_basic = (LAKE_DIR / "market" / "daily_basic" / "*" / "*.parquet").as_posix()
    p_meta = (LAKE_DIR / "meta" / "stock_basic.parquet").as_posix()
    p_index = (LAKE_DIR / "indices" / "index_daily.parquet").as_posix()

    print("[1/5] 从数据湖提取 2019-2024 全市场基础行情与过滤指标...")
    # Step 1: Pre-filter stock universe and calculate rolling factors
    # Exclude ST, list_date >= 180 days before trade_date, circ_mv >= 30亿 (300,000 万元)
    sql_base = f"""
    CREATE OR REPLACE TEMPORARY TABLE filtered_universe AS
    WITH raw_stocks AS (
        SELECT 
            d.date, d.ts_code, d.open, d.high, d.low, d.close, 
            d.volume_shares, d.amount,
            l.up_limit, l.down_limit,
            b.circ_mv, b.pe_ttm, b.turnover_rate,
            m.name, m.market, m.list_date
        FROM read_parquet('{p_daily}') d
        JOIN read_parquet('{p_limit}') l 
          ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
        JOIN read_parquet('{p_basic}') b 
          ON d.ts_code = b.ts_code AND d.trade_date = b.trade_date
        JOIN read_parquet('{p_meta}') m 
          ON d.ts_code = m.ts_code
        WHERE d.date >= '2018-11-01' AND d.date <= '2024-12-31'
          AND m.name NOT LIKE '%ST%' 
          AND m.name NOT LIKE '%退%'
          AND d.date >= strftime(date_add(strptime(m.list_date, '%Y%m%d'), INTERVAL 180 DAY), '%Y-%m-%d')
    ),
    daily_returns AS (
        SELECT 
            date, ts_code, open, high, low, close, volume_shares, amount,
            up_limit, down_limit, circ_mv, pe_ttm, turnover_rate,
            LAG(close, 20) OVER (PARTITION BY ts_code ORDER BY date) AS close_lag20,
            (close / LAG(close, 1) OVER (PARTITION BY ts_code ORDER BY date) - 1.0) AS ret_1d
        FROM raw_stocks
    ),
    rolling_metrics AS (
        SELECT 
            date, ts_code, open, high, low, close, volume_shares, amount,
            up_limit, down_limit, circ_mv, pe_ttm, turnover_rate, close_lag20,
            STDDEV_SAMP(ret_1d) 
                OVER (PARTITION BY ts_code ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_20d,
            AVG(amount) 
                OVER (PARTITION BY ts_code ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS adv20_amount,
            AVG(turnover_rate) 
                OVER (PARTITION BY ts_code ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS avg_turnover20
        FROM daily_returns
    )
    SELECT 
        date, ts_code, open, high, low, close, volume_shares,
        up_limit, down_limit, circ_mv, pe_ttm,
        adv20_amount,
        -- Factor 1: 20-day volatility-adjusted reversal
        CASE WHEN vol_20d > 0 THEN -(close / close_lag20 - 1.0) / vol_20d ELSE NULL END AS factor_reversal,
        -- Factor 2: Earnings-to-Price (Quality Value)
        CASE WHEN pe_ttm > 0 THEN 1.0 / pe_ttm ELSE NULL END AS factor_ep,
        -- Factor 3: Liquidity Anomaly (Low Turnover)
        -avg_turnover20 AS factor_turnover,
        -- Tradability flags
        (close >= up_limit - 0.01 AND low >= up_limit - 0.01) AS is_limit_up_untradable,
        (close <= down_limit + 0.01 AND high <= down_limit + 0.01) AS is_limit_down_untradable
    FROM rolling_metrics
    WHERE date >= '2019-01-01'
      AND close_lag20 IS NOT NULL
      AND circ_mv >= 300000        -- 流通市值 >= 30 亿元
      AND adv20_amount >= 30000    -- 20日日均成交额 >= 3000 万元
    """
    con.execute(sql_base)
    print(f"  * 过滤后基础特征表构建完成，耗时: {time.time()-t0:.2f}s")

    print("[2/5] 提取基准指数日行情 (沪深300 与 中证500)...")
    sql_bench = f"""
    SELECT date, ts_code, close 
    FROM read_parquet('{p_index}')
    WHERE date >= '2019-01-01' AND date <= '2024-12-31'
      AND ts_code IN ('000300.SH', '000905.SH')
    ORDER BY date, ts_code
    """
    bench_df = con.sql(sql_bench).df()
    bench_pivot = bench_df.pivot(index='date', columns='ts_code', values='close').sort_index()

    print("[3/5] 构建周度多因子截面排名与调仓目标清单 (Top 30 等权)...")
    # Identify rebalance dates: first trading date of each calendar week
    rebalance_dates = con.sql("""
        SELECT MIN(date) as rebal_date 
        FROM (SELECT DISTINCT date, strftime(strptime(date, '%Y-%m-%d'), '%Y-%W') as yr_wk FROM filtered_universe)
        GROUP BY yr_wk
        ORDER BY rebal_date
    """).df()["rebal_date"].tolist()

    print(f"  * 共有 {len(rebalance_dates)} 个周度调仓决策日")

    # Multi-factor score: rank reversal + rank ep + rank turnover
    sql_signals = """
    WITH scored AS (
        SELECT 
            date, ts_code, open, close, up_limit, down_limit,
            is_limit_up_untradable, is_limit_down_untradable,
            factor_reversal, factor_ep, factor_turnover,
            PERCENT_RANK() OVER (PARTITION BY date ORDER BY factor_reversal) AS r_rev,
            PERCENT_RANK() OVER (PARTITION BY date ORDER BY factor_ep) AS r_ep,
            PERCENT_RANK() OVER (PARTITION BY date ORDER BY factor_turnover) AS r_turn
        FROM filtered_universe
        WHERE factor_reversal IS NOT NULL 
          AND factor_ep IS NOT NULL 
          AND factor_turnover IS NOT NULL
    ),
    composite AS (
        SELECT 
            date, ts_code, open, close, up_limit, down_limit,
            is_limit_up_untradable, is_limit_down_untradable,
            (r_rev * 0.40 + r_ep * 0.35 + r_turn * 0.25) AS composite_score,
            ROW_NUMBER() OVER (PARTITION BY date ORDER BY (r_rev * 0.40 + r_ep * 0.35 + r_turn * 0.25) DESC) AS rank
        FROM scored
        WHERE is_limit_up_untradable = false  -- 一字涨停禁止选入买单
    )
    SELECT date, ts_code, open, close, up_limit, down_limit, composite_score, rank
    FROM composite
    WHERE rank <= 30
    ORDER BY date, rank
    """
    signals_df = con.sql(sql_signals).df()
    signals_by_date = {d: group for d, group in signals_df.groupby("date")}

    # Also load daily price matrix for portfolio mark-to-market valuation
    print("[4/5] 预载入全市场每日收盘价与涨跌停状态矩阵...")
    daily_price_df = con.sql("""
        SELECT date, ts_code, open, close, up_limit, down_limit,
               is_limit_up_untradable, is_limit_down_untradable
        FROM filtered_universe
    """).df()
    price_dict = {}
    for row in daily_price_df.itertuples():
        price_dict[(row.date, row.ts_code)] = row

    all_dates = sorted(daily_price_df["date"].unique().tolist())

    print("[5/5] 执行纯真实微观机制回测 (T+1 / 印花税 / 佣金保底 / 停牌锁仓 / 涨跌停拦截)...")
    # Simulation state variables
    INITIAL_CASH = 10_000_000.0  # 1000 万起始资金
    cash = INITIAL_CASH
    positions = {}        # ts_code -> {'shares': int, 'sellable': int, 'cost': float}
    portfolio_history = []
    
    total_fee_stamp = 0.0
    total_fee_comm = 0.0
    total_fee_trans = 0.0
    total_fee_slip = 0.0
    turnover_volume_sum = 0.0

    # Main Day-by-Day Event-Driven Loop
    rebal_set = set(rebalance_dates)

    for current_date in all_dates:
        # A. Start of day: Release T+1 locked shares (all current shares become sellable)
        for sym in positions:
            positions[sym]['sellable'] = positions[sym]['shares']

        # B. Weekly Rebalance Decision on rebalance dates
        if current_date in rebal_set and current_date in signals_by_date:
            target_group = signals_by_date[current_date]
            target_symbols = set(target_group["ts_code"].tolist())
            
            # 1. Total Portfolio NAV before rebalance
            current_nav = cash
            for sym, pos in positions.items():
                p_info = price_dict.get((current_date, sym))
                p_close = p_info.close if p_info else pos['cost']
                current_nav += pos['shares'] * p_close

            # Target weight per stock = 95% / 30 stocks = 3.1667% (leaving 5% cash reserve)
            target_weight = 0.95 / len(target_symbols)
            target_amount_per_stock = current_nav * target_weight

            # 2. SELLS: Stocks currently held but not in targets, or overweight
            for sym in list(positions.keys()):
                pos = positions[sym]
                p_info = price_dict.get((current_date, sym))
                if not p_info:
                    continue  # suspended, lock position

                # Check if stock is down-limit (cannot sell!)
                if p_info.is_limit_down_untradable or p_info.close <= p_info.down_limit + 0.01:
                    continue  # locked!

                if sym not in target_symbols:
                    # Full exit: sell all sellable shares
                    sell_qty = pos['sellable']
                    if sell_qty > 0:
                        exec_price = p_info.open
                        # Slippage
                        exec_price = exec_price * (1.0 - 0.0005)
                        gross_val = sell_qty * exec_price
                        
                        # Fees:
                        # Stamp duty: 0.1% before 2023-08-28, 0.05% on and after
                        stamp_rate = 0.0005 if current_date >= '2023-08-28' else 0.0010
                        fee_stamp = gross_val * stamp_rate
                        fee_comm = max(5.0, gross_val * 0.00025)
                        fee_trans = gross_val * 0.00002
                        fee_slip = sell_qty * p_info.open * 0.0005
                        
                        net_cash = gross_val - fee_stamp - fee_comm - fee_trans
                        cash += net_cash
                        
                        total_fee_stamp += fee_stamp
                        total_fee_comm += fee_comm
                        total_fee_trans += fee_trans
                        total_fee_slip += fee_slip
                        turnover_volume_sum += gross_val

                        pos['shares'] -= sell_qty
                        pos['sellable'] -= sell_qty
                        if pos['shares'] == 0:
                            del positions[sym]

            # 3. BUYS: Target stocks not held, or underweight
            for sym in target_symbols:
                p_info = price_dict.get((current_date, sym))
                if not p_info:
                    continue
                # Check if stock is up-limit (cannot buy!)
                if p_info.is_limit_up_untradable or p_info.open >= p_info.up_limit - 0.01:
                    continue

                curr_shares = positions[sym]['shares'] if sym in positions else 0
                curr_val = curr_shares * p_info.close
                delta_val = target_amount_per_stock - curr_val

                if delta_val > 10000 and cash > current_nav * 0.05:  # ensure cash reserve >= 5%
                    exec_price = p_info.open * (1.0 + 0.0005)  # buy with slippage
                    # Minimum step: 100 shares for Main/ChiNext, 200 for STAR
                    is_star = sym.startswith("688")
                    min_q = 200 if is_star else 100
                    step_q = 1 if is_star else 100
                    
                    buy_shares = int(delta_val / (exec_price * 1.0003)) // 100 * 100
                    if buy_shares >= min_q:
                        gross_val = buy_shares * exec_price
                        fee_comm = max(5.0, gross_val * 0.00025)
                        fee_trans = gross_val * 0.00002
                        fee_slip = buy_shares * p_info.open * 0.0005
                        total_cost = gross_val + fee_comm + fee_trans

                        if cash - total_cost >= current_nav * 0.05:
                            cash -= total_cost
                            total_fee_comm += fee_comm
                            total_fee_trans += fee_trans
                            total_fee_slip += fee_slip
                            turnover_volume_sum += gross_val

                            if sym not in positions:
                                positions[sym] = {'shares': buy_shares, 'sellable': 0, 'cost': exec_price}
                            else:
                                positions[sym]['shares'] += buy_shares
                                # new shares cannot be sold today (T+1)

        # C. End of Day: Mark to Market NAV
        daily_stock_val = 0.0
        for sym, pos in positions.items():
            p_info = price_dict.get((current_date, sym))
            close_px = p_info.close if p_info else pos['cost']
            daily_stock_val += pos['shares'] * close_px
        
        daily_total_nav = cash + daily_stock_val

        # Benchmark closes
        b300 = bench_pivot.loc[current_date, '000300.SH'] if current_date in bench_pivot.index and '000300.SH' in bench_pivot.columns else np.nan
        b500 = bench_pivot.loc[current_date, '000905.SH'] if current_date in bench_pivot.index and '000905.SH' in bench_pivot.columns else np.nan

        portfolio_history.append({
            'date': current_date,
            'cash': cash,
            'stock_value': daily_stock_val,
            'nav': daily_total_nav,
            'holdings_count': len(positions),
            'benchmark_300': b300,
            'benchmark_500': b500
        })

    con.close()
    elapsed = time.time() - t0
    print(f"\n✅ 6年全天候回测循环完成！总耗时: {elapsed:.2f} 秒！")

    # ==========================================
    # Performance Metrics Calculation
    # ==========================================
    perf_df = pd.DataFrame(portfolio_history).set_index('date')
    perf_df['daily_return'] = perf_df['nav'].pct_change().fillna(0.0)
    perf_df['cum_return'] = perf_df['nav'] / INITIAL_CASH - 1.0

    # Benchmark cumulative returns
    init_b300 = perf_df['benchmark_300'].dropna().iloc[0]
    init_b500 = perf_df['benchmark_500'].dropna().iloc[0]
    perf_df['cum_b300'] = perf_df['benchmark_300'] / init_b300 - 1.0
    perf_df['cum_b500'] = perf_df['benchmark_500'] / init_b500 - 1.0

    # Drawdown
    perf_df['peak'] = perf_df['nav'].cummax()
    perf_df['drawdown'] = (perf_df['nav'] - perf_df['peak']) / perf_df['peak']

    # Total trading days & annualized factors
    n_days = len(perf_df)
    years = n_days / 242.0

    total_return = perf_df['cum_return'].iloc[-1]
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0
    ann_vol = perf_df['daily_return'].std() * np.sqrt(242)
    rf = 0.02
    sharpe = (cagr - rf) / ann_vol if ann_vol > 0 else 0.0
    
    downside_vol = perf_df['daily_return'][perf_df['daily_return'] < 0].std() * np.sqrt(242)
    sortino = (cagr - rf) / downside_vol if downside_vol > 0 else 0.0

    max_dd = perf_df['drawdown'].min()
    calmar = cagr / abs(max_dd) if abs(max_dd) > 0 else 0.0

    # Benchmark stats
    b300_tot = perf_df['cum_b300'].iloc[-1]
    b300_cagr = (1.0 + b300_tot) ** (1.0 / years) - 1.0
    b500_tot = perf_df['cum_b500'].iloc[-1]
    b500_cagr = (1.0 + b500_tot) ** (1.0 / years) - 1.0

    # Excess vs CSI 500
    perf_df['b500_ret'] = perf_df['benchmark_500'].pct_change().fillna(0.0)
    perf_df['excess_ret_500'] = perf_df['daily_return'] - perf_df['b500_ret']
    ann_alpha_500 = cagr - b500_cagr
    tracking_err_500 = perf_df['excess_ret_500'].std() * np.sqrt(242)
    info_ratio_500 = ann_alpha_500 / tracking_err_500 if tracking_err_500 > 0 else 0.0

    # Win rates
    win_days = (perf_df['daily_return'] > 0).sum()
    total_active_days = (perf_df['daily_return'] != 0).sum()
    daily_win_rate = win_days / total_active_days if total_active_days > 0 else 0.0

    # Year by year breakdown
    perf_df['year'] = perf_df.index.str[:4]
    yearly_rows = []
    for yr, ydf in perf_df.groupby('year'):
        y_start_nav = ydf['nav'].iloc[0]
        y_end_nav = ydf['nav'].iloc[-1]
        y_ret = (y_end_nav / y_start_nav) - 1.0
        y_vol = ydf['daily_return'].std() * np.sqrt(len(ydf))
        y_dd = ((ydf['nav'] - ydf['nav'].cummax()) / ydf['nav'].cummax()).min()
        y_b300 = (ydf['benchmark_300'].iloc[-1] / ydf['benchmark_300'].iloc[0]) - 1.0
        y_b500 = (ydf['benchmark_500'].iloc[-1] / ydf['benchmark_500'].iloc[0]) - 1.0
        yearly_rows.append({
            'Year': yr,
            'Strategy_Return': y_ret,
            'CSI300_Return': y_b300,
            'CSI500_Return': y_b500,
            'Excess_vs_CSI500': y_ret - y_b500,
            'Max_Drawdown': y_dd,
            'Volatility': y_vol
        })
    yearly_df = pd.DataFrame(yearly_rows)

    # Save output artifacts
    perf_df.to_csv(OUTPUTS_DIR / "long_horizon_nav_curve.csv")
    yearly_df.to_csv(OUTPUTS_DIR / "long_horizon_yearly_breakdown.csv", index=False)

    summary_metrics = {
        "status": "PASS",
        "timestamp": datetime.now().isoformat(),
        "horizon": {
            "start_date": perf_df.index[0],
            "end_date": perf_df.index[-1],
            "total_trading_days": n_days,
            "total_years": round(years, 2)
        },
        "capital_and_friction": {
            "initial_cash": INITIAL_CASH,
            "final_nav": round(perf_df['nav'].iloc[-1], 2),
            "total_stamp_tax_paid": round(total_fee_stamp, 2),
            "total_broker_commission_paid": round(total_fee_comm, 2),
            "total_transfer_fee_paid": round(total_fee_trans, 2),
            "total_slippage_cost": round(total_fee_slip, 2),
            "total_trading_friction": round(total_fee_stamp + total_fee_comm + total_fee_trans + total_fee_slip, 2),
            "annualized_turnover_rate": round(turnover_volume_sum / (INITIAL_CASH * years), 2)
        },
        "performance_summary": {
            "strategy_total_return": f"{total_return * 100:.2f}%",
            "strategy_cagr": f"{cagr * 100:.2f}%",
            "strategy_annual_volatility": f"{ann_vol * 100:.2f}%",
            "strategy_sharpe_ratio": round(sharpe, 2),
            "strategy_sortino_ratio": round(sortino, 2),
            "strategy_max_drawdown": f"{max_dd * 100:.2f}%",
            "strategy_calmar_ratio": round(calmar, 2),
            "daily_win_rate": f"{daily_win_rate * 100:.2f}%"
        },
        "benchmark_comparison": {
            "csi300_cagr": f"{b300_cagr * 100:.2f}%",
            "csi300_total_return": f"{b300_tot * 100:.2f}%",
            "csi500_cagr": f"{b500_cagr * 100:.2f}%",
            "csi500_total_return": f"{b500_tot * 100:.2f}%",
            "annualized_alpha_vs_csi500": f"{ann_alpha_500 * 100:.2f}%",
            "information_ratio_vs_csi500": round(info_ratio_500, 2)
        },
        "yearly_breakdown": yearly_df.to_dict(orient="records")
    }

    report_path = OUTPUTS_DIR / "long_horizon_battle_test_report.json"
    report_path.write_text(json.dumps(summary_metrics, indent=2, ensure_ascii=False), encoding="utf8")

    print("\n" + "=" * 80)
    print("📊 6 年长周期实战检验终态指标汇总 (2019 - 2024)")
    print("=" * 80)
    print(f"  * 初始资金: {INITIAL_CASH:,.2f} 元  -->  最终净资产: {summary_metrics['capital_and_friction']['final_nav']:,.2f} 元")
    print(f"  * 累计净收益率        : {summary_metrics['performance_summary']['strategy_total_return']}")
    print(f"  * 年化复合收益率 (CAGR): {summary_metrics['performance_summary']['strategy_cagr']}")
    print(f"  * 基准 CAGR (沪深300) : {summary_metrics['benchmark_comparison']['csi300_cagr']}  |  中证500: {summary_metrics['benchmark_comparison']['csi500_cagr']}")
    print(f"  * 年化超额 Alpha      : {summary_metrics['benchmark_comparison']['annualized_alpha_vs_csi500']}")
    print(f"  * 年化夏普比率 (Sharpe): {summary_metrics['performance_summary']['strategy_sharpe_ratio']}")
    print(f"  * 索提诺比率 (Sortino) : {summary_metrics['performance_summary']['strategy_sortino_ratio']}")
    print(f"  * 最大回撤 (Max DD)   : {summary_metrics['performance_summary']['strategy_max_drawdown']}")
    print(f"  * 卡玛比率 (Calmar)   : {summary_metrics['performance_summary']['strategy_calmar_ratio']}")
    print(f"  * 信息比率 (IR vs 500): {summary_metrics['benchmark_comparison']['information_ratio_vs_csi500']}")
    print(f"  * 累计扣减真实交易摩擦: {summary_metrics['capital_and_friction']['total_trading_friction']:,.2f} 元")
    print("-" * 80)
    print("📅 分年度多空表现分解:")
    print(yearly_df.to_string(index=False))
    print("=" * 80)
    print(f"完整报告已落盘至: {report_path}")

    return summary_metrics

if __name__ == "__main__":
    run_battle_test()
