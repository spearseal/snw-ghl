import { TrendingUp, AlertTriangle, Database, Snowflake } from 'lucide-react';

export interface KpiData {
  key: string;
  label: string;
  value: string | number;
  source: string;
  detail?: string;
  trend?: string | null;
  format?: string;
}

const SOURCE_STYLES: Record<string, { bg: string; text: string; icon: typeof Database }> = {
  GoHighLevel: { bg: 'from-violet-600/20 to-violet-900/10', text: 'text-violet-300', icon: Database },
  Snowflake: { bg: 'from-sky-600/20 to-sky-900/10', text: 'text-sky-300', icon: Snowflake },
  'GoHighLevel + Snowflake': {
    bg: 'from-indigo-600/20 to-emerald-900/10',
    text: 'text-indigo-300',
    icon: TrendingUp,
  },
};

export default function KpiCard({ kpi }: { kpi: KpiData }) {
  const style = SOURCE_STYLES[kpi.source] || SOURCE_STYLES['GoHighLevel + Snowflake'];
  const Icon = style.icon;
  const isAttention = kpi.trend === 'attention';

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-5 transition hover:border-slate-600 ${
        isAttention
          ? 'border-amber-700/50 from-amber-950/30 to-slate-900/60'
          : `border-slate-800 ${style.bg}`
      }`}
    >
      {isAttention && (
        <AlertTriangle className="absolute right-4 top-4 h-4 w-4 text-amber-400" />
      )}
      <div className="mb-3 flex items-center gap-2">
        <Icon className={`h-4 w-4 ${isAttention ? 'text-amber-400' : style.text}`} />
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
            isAttention ? 'bg-amber-900/40 text-amber-300' : 'bg-slate-800/80 text-slate-400'
          }`}
        >
          {kpi.source}
        </span>
      </div>
      <p className="text-3xl font-bold tracking-tight text-slate-50">{kpi.value}</p>
      <p className="mt-1 text-sm font-medium text-slate-200">{kpi.label}</p>
      {kpi.detail && (
        <p className="mt-2 text-xs leading-relaxed text-slate-500">{kpi.detail}</p>
      )}
    </div>
  );
}
