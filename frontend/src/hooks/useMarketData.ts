import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { marketService, MarketOverviewResponse, type MarketId } from '../services/marketService';

export interface UseMarketDataOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
  market?: MarketId;
  timeoutMs?: number;
}

export interface UseMarketDataReturn {
  data: MarketOverviewResponse | null;
  loading: boolean;
  error: string | null;
  lastUpdate: string | null;
  refresh: () => void;
  isConnected: boolean;
  timedOut: boolean;
}

export const useMarketData = (options: UseMarketDataOptions = {}): UseMarketDataReturn => {
  const {
    autoRefresh = true,
    refreshInterval = 5000, // 5秒
    market = 'CN',
    timeoutMs = 8000, // 默认 8 秒超时（匹配腾讯财经 REQUEST_TIMEOUT）
  } = options;

  const [timedOut, setTimedOut] = useState(false);

  const { data, error, isLoading, isError, refetch } = useQuery<MarketOverviewResponse, Error>({
    queryKey: ['marketData', market],
    queryFn: async () => {
      const response = await marketService.getMarketOverview(market);
      if (response.success && response.data) {
        return response.data;
      }
      return { indices: [], lastUpdate: '', count: 0 };
    },
    refetchInterval: autoRefresh ? refreshInterval : false,
    refetchOnWindowFocus: true,
  });

  // 超时兜底：仅控制展示，不丢弃进行中的请求。
  useEffect(() => {
    if (!isLoading) {
      setTimedOut(false);
      return;
    }
    const timer = setTimeout(() => setTimedOut(true), timeoutMs);
    return () => clearTimeout(timer);
  }, [isLoading, timeoutMs]);

  return {
    data: data || null,
    loading: isLoading,
    error: error ? error.message : null,
    lastUpdate: data ? new Date().toISOString() : null,
    refresh: refetch,
    isConnected: !isError,
    timedOut,
  };
};
