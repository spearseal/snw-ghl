'use client';

import { TrendingDown, TrendingUp } from 'lucide-react';

export interface DecisionFactor {
  key: string;
  label: string;
  value: string | number;
  impact: 'high' | 'medium' | 'low' | string;
  recommendation: string;
  trend?: string | null;
}

export interface MonthlyRevenue {
  month: string;
  new_contacts: number;
  won_revenue: number;
  won_count: number;
  lost_count: number;
  open_pipeline_value: number;
  open_count: number;
  stale_opportunities: number;
  inactive_patients: number;
  decision_factors: DecisionFactor[];
}

const IMPACT_STYLES: Record<string, string> = {
  high: 'border-red-200 bg-red-50 dark:border-red-800/50 dark:bg-red-950/30',
  medium: 'border-amber-200 bg-amber-50 dark:border-amber-800/50 dark:bg-amber-950/30',
  low: 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/40',
};

export function RevenueFactorCards({ factors }: { factors: DecisionFactor[] }) {
  if (!factors.length) {
    return <p className="text-sm text-slate-500">No decision factors for this period.</p>;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {factors.map((factor) => (
        <div
          key={factor.key}
          className={`rounded-xl border p-4 ${IMPACT_STYLES[factor.impact] || IMPACT_STYLES.low}`}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {factor.label}
            </span>
            <span className="text-[10px] uppercase text-slate-400">{factor.impact} impact</span>
          </div>
          <p className="flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-slate-50">
            {factor.value}
            {factor.trend === 'up' && <TrendingUp className="h-4 w-4 text-emerald-500" />}
            {factor.trend === 'down' && <TrendingDown className="h-4 w-4 text-red-500" />}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
            {factor.recommendation}
          </p>
        </div>
      ))}
    </div>
  );
}

export function MonthlyRevenueTable({ monthly }: { monthly: MonthlyRevenue[] }) {
  const recent = [...monthly].reverse().slice(0, 6);

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-slate-100 text-xs uppercase text-slate-500 dark:bg-slate-900">
          <tr>
            <th className="px-4 py-2">Month</th>
            <th className="px-4 py-2">Won revenue</th>
            <th className="px-4 py-2">New leads</th>
            <th className="px-4 py-2">Won / Lost</th>
            <th className="px-4 py-2">Stale deals</th>
          </tr>
        </thead>
        <tbody>
          {recent.map((row) => (
            <tr key={row.month} className="border-t border-slate-200 dark:border-slate-800">
              <td className="px-4 py-2 font-medium text-slate-800 dark:text-slate-200">{row.month}</td>
              <td className="px-4 py-2 text-emerald-600 dark:text-emerald-400">
                ${row.won_revenue.toLocaleString()}
              </td>
              <td className="px-4 py-2">{row.new_contacts}</td>
              <td className="px-4 py-2">
                {row.won_count} / {row.lost_count}
              </td>
              <td className="px-4 py-2 text-amber-600 dark:text-amber-400">
                {row.stale_opportunities}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
