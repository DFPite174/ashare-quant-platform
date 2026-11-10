import { describe, expect, it } from 'vitest';
import {
  DEFAULT_CONTEXT,
  DEFAULT_FACTOR_FILTER,
  DEFAULT_PARAMS,
  DEFAULT_TARGET,
  buildTrainingConfigFile,
  parseTrainingConfig,
  serializeTrainingConfig,
  type TrainingDraft,
  type TrainingConfigFilterNode,
} from '../trainingUtils';

const draft: Omit<TrainingDraft, 'lastSavedAt'> = {
  displayName: '往返测试',
  displayNameMode: 'manual',
  selectedFeatures: ['mom_ret_1d', 'mom_ret_5d'],
  timePeriods: {
    train: ['2018-01-02', '2023-06-18'],
    val: ['2023-06-22', '2025-01-21'],
    test: ['2025-01-25', '2026-08-28'],
  },
  target: DEFAULT_TARGET,
  params: DEFAULT_PARAMS,
  context: DEFAULT_CONTEXT,
  wfa: { enabled: false, strategy: 'rolling', nWindows: 4, trainYears: 3, valMonths: 12, stepMonths: 12 },
};

/** 直接拼配置文件，绕开 builder，以便构造畸形 factor_filter。 */
const serializeRaw = (factorFilter?: unknown) =>
  serializeTrainingConfig({
    schema_version: 1,
    kind: 'quantmind-model-training-config',
    exported_at: new Date().toISOString(),
    market: 'CN',
    ...(factorFilter === undefined
      ? {}
      : { factor_filter: factorFilter as TrainingConfigFilterNode }),
    configuration: draft,
  });

describe('模型训练配置文件的因子筛选节点', () => {
  it('导出再导入后保留 factor_filter', () => {
    const text = serializeTrainingConfig(
      buildTrainingConfigFile(draft, {
        market: 'CN',
        factor_source: 'l1_l2_factors',
        factor_catalog_version: 'qdb-cn-l1_l2_factors-9783e05ac172',
        factor_filter: { ...DEFAULT_FACTOR_FILTER, nTop: 120 },
      }),
    );

    expect(text).toContain('n_top: 120');

    const parsed = parseTrainingConfig(text);
    expect(parsed.factorFilter).toEqual({ ...DEFAULT_FACTOR_FILTER, nTop: 120 });
    expect(parsed.factorSource).toBe('l1_l2_factors');
    expect(parsed.factorCatalogVersion).toBe('qdb-cn-l1_l2_factors-9783e05ac172');
  });

  it('不含 factor_filter 的旧配置仍可导入，返回 undefined 以沿用表单当前值', () => {
    const parsed = parseTrainingConfig(
      serializeTrainingConfig(buildTrainingConfigFile(draft, { market: 'CN' })),
    );

    expect(parsed.factorFilter).toBeUndefined();
  });

  it('n_top 越界被钳制到 [10, 300]', () => {
    expect(parseTrainingConfig(serializeRaw({ n_top: 999 })).factorFilter?.nTop).toBe(300);
    expect(parseTrainingConfig(serializeRaw({ n_top: 1 })).factorFilter?.nTop).toBe(10);
    expect(parseTrainingConfig(serializeRaw({ n_top: 120 })).factorFilter?.nTop).toBe(120);
  });

  it('缺失或非法字段回落默认值，不抛错', () => {
    const parsed = parseTrainingConfig(serializeRaw({ n_top: 'abc' }));

    expect(parsed.factorFilter?.nTop).toBe(DEFAULT_FACTOR_FILTER.nTop);
    expect(parsed.factorFilter?.icThreshold).toBe(DEFAULT_FACTOR_FILTER.icThreshold);
    expect(parsed.factorFilter?.icirThreshold).toBe(DEFAULT_FACTOR_FILTER.icirThreshold);
    expect(parsed.factorFilter?.correlationThreshold).toBe(DEFAULT_FACTOR_FILTER.correlationThreshold);
    expect(parsed.factorFilter?.enabled).toBe(DEFAULT_FACTOR_FILTER.enabled);
  });

  it('factor_filter 不是对象时视为未提供', () => {
    expect(parseTrainingConfig(serializeRaw('not-an-object')).factorFilter).toBeUndefined();
    expect(parseTrainingConfig(serializeRaw([1, 2, 3])).factorFilter).toBeUndefined();
  });
});
