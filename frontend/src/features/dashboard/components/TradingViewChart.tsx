import React, { useEffect, useRef } from 'react';
import {
    createChart,
    CandlestickSeries,
    HistogramSeries,
    type IChartApi,
    type ISeriesApi,
} from 'lightweight-charts';
import type { KlineItem } from '../services/dataDashboardService';

interface TradingViewChartProps {
  data: KlineItem[];
  height?: number;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({ data, height = 550 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  // 图表实例只建一次：data 变化只 setData，避免切换市场时整实例重建掉帧
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 0, // Normal
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: false,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    candleRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#10b981',
      borderUpColor: '#ef4444',
      borderDownColor: '#10b981',
      wickUpColor: '#ef4444',
      wickDownColor: '#10b981',
    });

    // Volume series
    volumeRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    const chart = chartRef.current;
    const candleSeries = candleRef.current;
    const volumeSeries = volumeRef.current;
    if (!chart || !candleSeries || !volumeSeries) return;

    const candleData = (data || []).map((d) => ({
      time: d.date as string,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    const volumeData = (data || []).map((d) => ({
      time: d.date as string,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(239,68,68,0.4)' : 'rgba(16,185,129,0.4)',
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);
    if (candleData.length > 0) {
      chart.timeScale().fitContent();
    }
  }, [data]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: `${height}px`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    />
  );
};
