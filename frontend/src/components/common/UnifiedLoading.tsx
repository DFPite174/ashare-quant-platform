/**
 * 统一加载态（三档）
 *
 * - PageLoading：全屏（启动 / 鉴权 / 品牌页）
 * - RouteFallback：路由懒加载 Suspense
 * - SectionLoading：页内区块
 *
 * 内容形骨架（仪表盘卡片）仍用 CardSkeletons；长任务遮罩仍用 LoadingModal。
 */

import React from 'react';
import { Spin } from 'antd';

const BRAND_GRADIENT =
  'linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #f5576c 75%, #4facfe 100%)';

export type PageLoadingVariant = 'brand' | 'app';

export interface PageLoadingProps {
  message?: string;
  /** brand=登录前紫粉渐变；app=应用内主题背景 */
  variant?: PageLoadingVariant;
  brandTitle?: string;
  fullViewport?: boolean;
}

/** 全屏页加载：启动恢复、鉴权、认证页初始化 */
export const PageLoading: React.FC<PageLoadingProps> = ({
  message = '加载中...',
  variant = 'app',
  brandTitle = 'QuantMind',
  fullViewport = true,
}) => {
  const isBrand = variant === 'brand';
  return (
    <div
      style={{
        minHeight: fullViewport ? '100vh' : '100%',
        height: fullViewport ? undefined : '100%',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: isBrand ? BRAND_GRADIENT : 'var(--bg-gradient, #f8fafc)',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{ textAlign: 'center' }}>
        {isBrand && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              marginBottom: 20,
              color: 'white',
            }}
          >
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                letterSpacing: '-0.02em',
              }}
            >
              {brandTitle}
            </div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>{message}</div>
          </div>
        )}
        <Spin size="large" />
        {!isBrand && (
          <div
            style={{
              marginTop: 16,
              fontSize: 13,
              color: 'var(--text-secondary, #64748b)',
            }}
          >
            {message}
          </div>
        )}
      </div>
    </div>
  );
};

export interface RouteFallbackProps {
  message?: string;
  /** 填满父容器（管理后台内页）而非整屏 */
  fill?: boolean;
}

/** 路由 / lazy Suspense 统一兜底 */
export const RouteFallback: React.FC<RouteFallbackProps> = ({
  message = '加载中...',
  fill = true,
}) => (
  <div
    className={fill ? 'w-full h-full min-h-[240px]' : undefined}
    style={{
      minHeight: fill ? undefined : '100vh',
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: 12,
      background: fill ? 'transparent' : 'var(--bg-gradient, #f8fafc)',
    }}
  >
    <Spin size="large" />
    <span style={{ fontSize: 13, color: 'var(--text-secondary, #64748b)' }}>{message}</span>
  </div>
);

export interface SectionLoadingProps {
  tip?: string;
  size?: 'small' | 'default' | 'large';
  className?: string;
  minHeight?: number | string;
}

/** 页内区块加载 */
export const SectionLoading: React.FC<SectionLoadingProps> = ({
  tip,
  size = 'large',
  className = '',
  minHeight = 160,
}) => (
  <div
    className={`flex flex-col items-center justify-center gap-3 w-full ${className}`}
    style={{ minHeight }}
  >
    <Spin size={size} />
    {tip ? (
      <span
        className={
          size === 'small' ? 'text-xs text-slate-400' : 'text-[13px] text-slate-500'
        }
      >
        {tip}
      </span>
    ) : null}
  </div>
);

/** 兼容旧 `Loading` API（自绘圆环 → 统一 Spin） */
export const Loading: React.FC<{
  size?: 'small' | 'medium' | 'large';
  text?: string;
}> = ({ size = 'medium', text }) => {
  const spinSize = size === 'small' ? 'small' : size === 'large' ? 'large' : 'default';
  return <SectionLoading tip={text} size={spinSize} minHeight={size === 'small' ? 64 : 120} />;
};

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-gray-200 rounded ${className}`} />
);

export default {
  PageLoading,
  RouteFallback,
  SectionLoading,
  Loading,
  Skeleton,
};
