/**
 * 标签管理（管理员）
 *
 * 对 finance_lexicon 表的 CRUD 操作：查看 / 新增 / 编辑 / 删除 / 启禁用
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  CloudUploadOutlined,
  DeleteOutlined,
  EditOutlined,
  InboxOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { newsService, type LexiconTag } from '../../news/services/newsService';

const { Title, Text } = Typography;

const KIND_OPTIONS = [
  { value: 'sentiment_pos', label: '情感(利好)' },
  { value: 'sentiment_neg', label: '情感(利空)' },
  { value: 'event', label: '事件/实体' },
  { value: 'department', label: '部门' },
];

const EVENT_TAG_OPTIONS = [
  { value: '国家', label: '国家' },
  { value: '地区', label: '地区' },
  { value: '省份', label: '省份' },
  { value: '城市', label: '城市' },
  { value: '领导人', label: '领导人' },
  { value: '调研', label: '调研' },
  { value: '部门', label: '部门' },
  { value: '产业', label: '产业' },
  { value: '政策', label: '政策' },
  { value: '地缘', label: '地缘' },
  { value: '外汇', label: '外汇' },
  { value: '加密', label: '加密' },
  { value: '财报', label: '财报' },
  { value: '市场', label: '市场' },
  { value: '宏观', label: '宏观' },
  { value: '期货', label: '期货' },
  { value: '监管', label: '监管' },
  { value: '行业板块', label: '行业板块' },
  { value: '概念板块', label: '概念板块' },
];

const KIND_LABEL_TO_VALUE: Record<string, string> = {
  '情感(利好)': 'sentiment_pos',
  '情感(利空)': 'sentiment_neg',
  '事件/实体': 'event',
  '部门': 'department',
  '利好': 'sentiment_pos',
  '利空': 'sentiment_neg',
};

function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let cur = '';
  let row: string[] = [];
  let inQuote = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuote) {
      if (c === '"') {
        if (text[i + 1] === '"') { cur += '"'; i++; }
        else inQuote = false;
      } else cur += c;
    } else {
      if (c === '"') inQuote = true;
      else if (c === ',') { row.push(cur.trim()); cur = ''; }
      else if (c === '\n') { row.push(cur.trim()); rows.push(row); row = []; cur = ''; }
      else if (c === '\r') { /* ignore */ }
      else cur += c;
    }
  }
  row.push(cur.trim());
  if (row.some((v) => v !== '')) rows.push(row);
  return rows.filter((r) => r.some((v) => v !== ''));
}

function normalizeKind(v: string): string {
  const s = (v || '').trim();
  if (!s) return 'event';
  if (KIND_OPTIONS.find((o) => o.value === s)) return s;
  if (KIND_LABEL_TO_VALUE[s]) return KIND_LABEL_TO_VALUE[s];
  const lower = s.toLowerCase();
  if (['sentiment_pos', 'pos', 'positive'].includes(lower)) return 'sentiment_pos';
  if (['sentiment_neg', 'neg', 'negative'].includes(lower)) return 'sentiment_neg';
  if (['department'].includes(lower)) return 'department';
  return 'event';
}

export const AdminTagManagement: React.FC = () => {
  const [tags, setTags] = useState<LexiconTag[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [filterEventTag, setFilterEventTag] = useState<string | undefined>();
  const [filterKind, setFilterKind] = useState<string | undefined>();
  const [filterKeyword, setFilterKeyword] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTag, setEditingTag] = useState<LexiconTag | null>(null);
  const [form] = Form.useForm();

  // CSV 导入解析
  const [importOpen, setImportOpen] = useState(false);
  const [importRows, setImportRows] = useState<Array<{ key: string; term: string; kind: string; event_tag: string | null; weight: number; note: string | null }>>([]);
  const [importFileName, setImportFileName] = useState('');
  const [importing, setImporting] = useState(false);

  const loadTags = useCallback(async () => {
    setLoading(true);
    try {
      const r = await newsService.adminListTags({
        page,
        page_size: pageSize,
        event_tag: filterEventTag,
        kind: filterKind,
        keyword: filterKeyword || undefined,
      });
      setTags(r.items ?? []);
      setTotal(r.total ?? 0);
    } catch {
      setTags([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterEventTag, filterKind, filterKeyword]);

  useEffect(() => {
    loadTags();
  }, [loadTags]);

  // 统计概览（基于当前加载列表前端统计；如需全局统计再加后端接口）
  const stats = useMemo(() => {
    const enabled = tags.filter((t) => t.enabled).length;
    const kindCount: Record<string, number> = {};
    tags.forEach((t) => {
      kindCount[t.kind] = (kindCount[t.kind] || 0) + 1;
    });
    const topKind = Object.entries(kindCount).sort((a, b) => b[1] - a[1])[0];
    const topKindLabel = topKind
      ? (KIND_OPTIONS.find((o) => o.value === topKind[0])?.label ?? topKind[0])
      : '—';
    return { enabled, disabled: total - enabled, topKind, topKindLabel };
  }, [tags, total]);

  const handleCreate = () => {
    setEditingTag(null);
    setModalOpen(true);
  };

  const handleEdit = (tag: LexiconTag) => {
    setEditingTag(tag);
    setModalOpen(true);
  };

  // destroyOnHidden 下 Form 在弹窗打开后才挂载；表单赋值必须在挂载之后进行，
  // 否则 useForm 实例未连接会告警且赋值丢失。
  useEffect(() => {
    if (!modalOpen) return;
    if (editingTag) {
      form.setFieldsValue({
        term: editingTag.term,
        kind: editingTag.kind,
        event_tag: editingTag.event_tag,
        weight: editingTag.weight,
        note: editingTag.note,
      });
    } else {
      form.resetFields();
      form.setFieldsValue({ kind: 'event', weight: 1.0, enabled: true });
    }
  }, [modalOpen, editingTag, form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editingTag) {
        await newsService.adminUpdateTag(editingTag.id, values);
        message.success('词条已更新');
      } else {
        await newsService.adminCreateTag(values);
        message.success('词条已创建');
      }
      setModalOpen(false);
      loadTags();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '操作失败';
      message.error(msg);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await newsService.adminDeleteTag(id);
      message.success('词条已删除');
      loadTags();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '删除失败';
      message.error(msg);
    }
  };

  const handleToggle = async (tag: LexiconTag) => {
    try {
      await newsService.adminToggleTag(tag.id);
      loadTags();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '操作失败';
      message.error(msg);
    }
  };

  // CSV 导入：解析表头自动填充
  const handleCSVFile = (file: File) => {
    setImportFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const raw = String(reader.result || '');
      // 去 BOM
      const text = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
      const rows = parseCSV(text);
      if (!rows.length) { message.warning('CSV 为空'); return; }
      const header = rows[0].map((h) => h.trim().toLowerCase());
      const hasHeader = header.some((h) => ['term', '词条', '词语', 'keyword'].includes(h) || ['kind', '类型'].includes(h));
      const dataRows = hasHeader ? rows.slice(1) : rows;
      const idx = (names: string[]) => {
        for (let i = 0; i < header.length; i++) if (names.includes(header[i])) return i;
        return -1;
      };
      const termIdx = hasHeader ? idx(['term', '词条', '词语', 'keyword', 'word']) : 0;
      const kindIdx = hasHeader ? idx(['kind', '类型']) : 1;
      const tagIdx = hasHeader ? idx(['event_tag', '标签', 'label', 'tag', '分类']) : 2;
      const weightIdx = hasHeader ? idx(['weight', '权重']) : 3;
      const noteIdx = hasHeader ? idx(['note', '备注', '说明']) : 4;
      const parsed = dataRows.map((r, i) => {
        const term = (r[termIdx >= 0 ? termIdx : 0] || '').trim();
        const kindRaw = (r[kindIdx >= 0 ? kindIdx : 1] || '').trim();
        const evt = (r[tagIdx >= 0 ? tagIdx : 2] || '').trim();
        const wRaw = (r[weightIdx >= 0 ? weightIdx : 3] || '').trim();
        const note = (r[noteIdx >= 0 ? noteIdx : 4] || '').trim() || null;
        return {
          key: String(i),
          term,
          kind: normalizeKind(kindRaw),
          event_tag: evt && EVENT_TAG_OPTIONS.find((o) => o.value === evt) ? evt : (EVENT_TAG_OPTIONS.find((o) => o.label === evt)?.value || null),
          weight: wRaw ? Number(wRaw) || 1 : 1,
          note,
        };
      }).filter((r) => r.term);
      if (!parsed.length) { message.warning('未解析到有效词条（首列需为词条）'); return; }
      setImportRows(parsed);
      message.success(`已解析 ${parsed.length} 条，自动填充字段`);
    };
    reader.readAsText(file, 'utf-8');
    return false;
  };

  const handleBatchImport = async () => {
    if (!importRows.length) { message.warning('请先导入 CSV'); return; }
    setImporting(true);
    let ok = 0; let fail = 0;
    for (const r of importRows) {
      try {
        await newsService.adminCreateTag({ term: r.term, kind: r.kind, event_tag: r.event_tag || undefined, weight: r.weight, note: r.note || undefined });
        ok++;
      } catch { fail++; }
    }
    setImporting(false);
    message.success(`批量导入完成：成功 ${ok} 条${fail ? `，失败 ${fail} 条` : ''}`);
    setImportOpen(false);
    setImportRows([]);
    setImportFileName('');
    loadTags();
  };

  const kindColor = (kind: string) => {
    if (kind === 'sentiment_pos') return 'red';
    if (kind === 'sentiment_neg') return 'green';
    if (kind === 'event') return 'blue';
    if (kind === 'department') return 'geekblue';
    return 'default';
  };

  const columns: ColumnsType<LexiconTag> = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 70,
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: '词条',
      dataIndex: 'term',
      width: 160,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'kind',
      width: 120,
      render: (v: string) => <Tag color={kindColor(v)}>{v}</Tag>,
    },
    {
      title: '标签',
      dataIndex: 'event_tag',
      width: 100,
      render: (v: string | null) => v ? <Tag>{v}</Tag> : <Text type="secondary">-</Text>,
    },
    {
      title: '权重',
      dataIndex: 'weight',
      width: 80,
      sorter: (a, b) => a.weight - b.weight,
    },
    {
      title: '备注',
      dataIndex: 'note',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'enabled',
      width: 80,
      render: (v: boolean, record) => (
        <Switch
          size="small"
          checked={v}
          onChange={() => handleToggle(record)}
        />
      ),
    },
    {
      title: '操作',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title="确定删除此词条？"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-4">
      {/* 顶部标题与统计 */}
      <div className="flex items-center justify-between pb-1">
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 700 }}>
            <TagsOutlined style={{ marginRight: 8, color: '#6366f1' }} />
            标签管理
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            新闻情感 / 事件词条词典（finance_lexicon）· 支持情感词、事件实体、部门词条维护
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadTags} style={{ borderRadius: 6 }}>刷新</Button>
          <Button icon={<CloudUploadOutlined />} onClick={() => setImportOpen(true)} style={{ borderRadius: 6 }}>导入 CSV</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ borderRadius: 6 }}>新增词条</Button>
        </Space>
      </div>

      {/* 统计概览卡片 */}
      <Row gutter={14}>
        <Col span={8}>
          <Card size="small" variant="borderless" style={{ background: '#eef2ff', borderRadius: 10 }}>
            <Statistic title="词条总数" value={total} suffix="条" valueStyle={{ color: '#4338ca', fontWeight: 700 }} style={{ textAlign: 'center' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" variant="borderless" style={{ background: '#f0fdf4', borderRadius: 10 }}>
            <Statistic title="已启用" value={stats.enabled} suffix="条" valueStyle={{ color: '#16a34a', fontWeight: 700 }} style={{ textAlign: 'center' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" variant="borderless" style={{ background: '#fff7ed', borderRadius: 10 }}>
            <Statistic title="最多类型" value={stats.topKindLabel} suffix={stats.topKind ? `(${stats.topKind[1]} 条)` : ''} valueStyle={{ color: '#d97706', fontWeight: 700 }} style={{ textAlign: 'center' }} />
          </Card>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <Card styles={{ body: { padding: 0 } }} style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid #e2e8f0' }}>
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-slate-100 bg-slate-50/50">
          <Select
            allowClear
            placeholder="按标签类型筛选"
            value={filterEventTag}
            onChange={(v) => { setFilterEventTag(v); setPage(1); }}
            options={EVENT_TAG_OPTIONS}
            style={{ minWidth: 160 }}
          />
          <Select
            allowClear
            placeholder="按情感/事件筛选"
            value={filterKind}
            onChange={(v) => { setFilterKind(v); setPage(1); }}
            options={KIND_OPTIONS}
            style={{ minWidth: 160 }}
          />
          {/* antd 5.29 的 Input.Search 内部仍走 addonAfter，触发自身废弃告警；
              等价改用 Space.Compact 组合，行为（回车/点击搜索）保持不变。 */}
          <Space.Compact style={{ width: 240 }}>
            <Input
              allowClear
              placeholder="搜索词条..."
              value={filterKeyword}
              onChange={(e) => setFilterKeyword(e.target.value)}
              onPressEnter={() => { setPage(1); loadTags(); }}
            />
            <Button icon={<SearchOutlined />} onClick={() => { setPage(1); loadTags(); }} />
          </Space.Compact>
        </div>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={tags}
          loading={loading}
          size="middle"
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
        />
      </Card>

      <Modal
        title={editingTag ? '编辑词条' : '新增词条'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
        styles={{
          content: { borderRadius: 24, padding: 0, overflow: 'hidden' },
          header: { padding: '16px 24px', margin: 0, borderBottom: '1px solid #f1f5f9' },
          body: { padding: 24 },
          footer: { padding: '12px 24px', borderTop: '1px solid #f1f5f9' },
        }}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 0 }}>
          <Form.Item name="term" label="词条" rules={[{ required: true, message: '请输入词条' }]}>
            <Input placeholder="如：国务院、央行、利好" />
          </Form.Item>
          <Form.Item name="kind" label="类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={KIND_OPTIONS} />
          </Form.Item>
          <Form.Item name="event_tag" label="标签分类">
            <Select allowClear options={EVENT_TAG_OPTIONS} placeholder="选择标签分类（可选）" />
          </Form.Item>
          <Form.Item name="weight" label="权重">
            <InputNumber min={0} max={10} step={0.1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} placeholder="备注说明（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* CSV 导入解析 — 自动填充字段 */}
      <Modal
        title={
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <CloudUploadOutlined />
            </div>
            <span className="font-black text-slate-800">导入词条 CSV</span>
          </div>
        }
        open={importOpen}
        onCancel={() => { setImportOpen(false); setImportRows([]); setImportFileName(''); }}
        onOk={handleBatchImport}
        okText={`确认导入 ${importRows.length ? `(${importRows.length} 条)` : ''}`}
        okButtonProps={{ disabled: !importRows.length, loading: importing, className: 'rounded-xl font-bold' }}
        cancelButtonProps={{ className: 'rounded-xl' }}
        width={860}
        destroyOnClose
        styles={{
          content: { borderRadius: 24, padding: 0, overflow: 'hidden' },
          header: { padding: '16px 24px', margin: 0, borderBottom: '1px solid #f1f5f9' },
          body: { padding: 24 },
          footer: { padding: '12px 24px', borderTop: '1px solid #f1f5f9' },
        }}
      >
        <div className="space-y-4">
          <Alert
            type="info"
            showIcon
            className="rounded-xl"
            message="支持 CSV 表头：term/词条, kind/类型, event_tag/标签, weight/权重, note/备注（大小写不敏感）"
            description={<span className="text-xs">无表头时按顺序解析 5 列；类型支持中英文与别名自动映射，缺省权重 1.0，未匹配标签自动置空。示例：<Text code>term,kind,event_tag,weight,note</Text> 首行</span>}
          />
          <Upload.Dragger
            accept=".csv,.txt"
            showUploadList={false}
            beforeUpload={handleCSVFile}
            className="rounded-xl"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">点击或拖拽 CSV 文件到此处</p>
            <p className="ant-upload-hint">支持 UTF-8 / GBK，自动识别表头并填充</p>
          </Upload.Dragger>
          {importFileName && <div className="text-xs text-slate-500">已选择：<Text code>{importFileName}</Text> · 已解析 {importRows.length} 条</div>}
          {importRows.length > 0 && (
            <Table
              rowKey="key"
              dataSource={importRows}
              size="small"
              pagination={{ pageSize: 8, showSizeChanger: false }}
              scroll={{ y: 260 }}
              columns={[
                { title: '词条', dataIndex: 'term', width: 160, render: (v: string) => <Text strong>{v}</Text> },
                { title: '类型', dataIndex: 'kind', width: 130, render: (v: string) => <Tag color={v === 'sentiment_pos' ? 'red' : v === 'sentiment_neg' ? 'green' : v === 'department' ? 'geekblue' : 'blue'}>{v}</Tag> },
                { title: '标签', dataIndex: 'event_tag', width: 100, render: (v: string | null) => v ? <Tag>{v}</Tag> : <Text type="secondary">—</Text> },
                { title: '权重', dataIndex: 'weight', width: 80 },
                { title: '备注', dataIndex: 'note', ellipsis: true, render: (v: string | null) => v || '—' },
              ]}
            />
          )}
        </div>
      </Modal>
    </div>
  );
};

export default AdminTagManagement;
