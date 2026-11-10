import React from 'react';

interface SectionCardProps {
  index: string;
  title: string;
  desc?: string;
  icon: React.ReactNode;
  tone?: 'indigo' | 'blue' | 'amber' | 'slate';
  children: React.ReactNode;
  extra?: React.ReactNode;
}

const toneMap: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-100', text: 'text-indigo-600', dot: 'bg-indigo-600' },
  blue: { bg: 'bg-blue-50', border: 'border-blue-100', text: 'text-blue-600', dot: 'bg-blue-600' },
  amber: { bg: 'bg-amber-50', border: 'border-amber-100', text: 'text-amber-600', dot: 'bg-amber-600' },
  slate: { bg: 'bg-slate-50', border: 'border-slate-100', text: 'text-slate-600', dot: 'bg-slate-600' },
};

export const SectionCard: React.FC<SectionCardProps> = ({ index, title, desc, icon, tone = 'slate', children, extra }) => {
  const t = toneMap[tone] || toneMap.slate;
  return (
    <div className="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 flex items-center justify-between border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-xl ${t.bg} ${t.border} border flex items-center justify-center ${t.text} text-base shrink-0`}>
            {icon}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-black tracking-widest text-slate-400">{index}</span>
              <h3 className="text-[14px] font-black text-slate-800 tracking-tight leading-none">{title}</h3>
            </div>
            {desc && <p className="text-xs text-slate-400 mt-1 leading-none">{desc}</p>}
          </div>
        </div>
        {extra && <div className="shrink-0">{extra}</div>}
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
};

interface VerticalStepProps {
  done: boolean;
  active?: boolean;
  title: string;
  desc?: string;
  extra?: React.ReactNode;
  isLast?: boolean;
}

export const VerticalStep: React.FC<VerticalStepProps> = ({ done, active, title, desc, extra, isLast }) => {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center shrink-0 w-6">
        <div
          className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-[11px] font-black transition-colors ${
            done ? 'bg-emerald-500 border-emerald-500 text-white' : active ? 'bg-white border-indigo-500 text-indigo-600' : 'bg-white border-slate-200 text-slate-300'
          }`}
        >
          {done ? '✓' : '•'}
        </div>
        {!isLast && <div className={`w-0.5 flex-1 mt-1 rounded-full ${done ? 'bg-emerald-200' : 'bg-slate-100'}`} style={{ minHeight: 32 }} />}
      </div>
      <div className={`flex-1 pb-6 ${isLast ? '!pb-0' : ''}`}>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-sm font-bold ${done ? 'text-slate-800' : active ? 'text-slate-800' : 'text-slate-500'}`}>{title}</span>
          {done
            ? <span className="text-[11px] font-bold px-1.5 py-0 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100">已完成</span>
            : active
              ? <span className="text-[11px] font-bold px-1.5 py-0 rounded-full bg-indigo-50 text-indigo-600 border border-indigo-100">进行中</span>
              : <span className="text-[11px] font-bold px-1.5 py-0 rounded-full bg-slate-50 text-slate-400 border border-slate-200">待完成</span>}
        </div>
        {desc && <p className="text-xs text-slate-400 mt-1 leading-relaxed">{desc}</p>}
        {extra && <div className="mt-3">{extra}</div>}
      </div>
    </div>
  );
};
