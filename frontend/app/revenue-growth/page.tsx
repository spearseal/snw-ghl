'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { DollarSign, Loader2, RefreshCw } from 'lucide-react';
import {
  MonthlyRevenueTable,
  RevenueFactorCards,
  type MonthlyRevenue,
  type DecisionFactor,
} from '@/components/revenue/RevenueGrowthPanel';
import { apiFetch, getToken } from '@/lib/api';

interface RevenueGrowthResponse {
  summary?: {
    current_month?: string;
    current_open_pipeline: number;
    current_open_deals: number;
    ytd_won_revenue: number;
    ytd_new_contacts: number;
    inactive_patients: number;
  };
  monthly?: MonthlyRevenue[];
  current_month_factors?: DecisionFactor[];
  source_label?: string;
  connected_sources?: Record<string, boolean>;
  errors?: Record<string, string>;
  message?: string;
  generated_at?: string;
}

export default function RevenueGrowthPage() {
  const router = useRouter();
  const [data, setData] = useState<RevenueGrowthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const loadRevenue = useCallback(async (passcode?: string) => {
    setError(null);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500', inactive_days: '90', months: '12' });
      if (passcode?.trim()) {
        params.set('snowflake_passcode', passcode.trim());
      }
      const res = await apiFetch(`/api/revenue/growth?${params.toString()}`, {}, 120_000);
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.detail || json.message || 'Failed to load revenue growth');
      }
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load revenue growth');
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    loadRevenue().finally(() => setLoading(false));
  }, [router, loadRevenue]);

  const refresh = async () => {
    setRefreshing(true);
    await loadRevenue(snowflakePasscode);
    setSnowflakePasscode('');
    setRefreshing(false);
  };

  const summary = data?.summary;
  const connected = data?.connected_sources || {};

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-emerald-500 dark:text-emerald-400">
            <DollarSign className="h-5 w-5" />
            <span className="text-xs font-medium uppercase tracking-wider">Revenue Intelligence</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Revenue Growth</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Monthly decision factors from Snowflake and GoHighLevel pipeline data.
            {data?.source_label && <span className="text-slate-500"> · {data.source_label}</span>}
            {data?.generated_at && (
              <span className="text-slate-500">
                {' '}
                · Updated {new Date(data.generated_at).toLocaleString()}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {connected.snowflake && (
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={snowflakePasscode}
              onChange={(e) => setSnowflakePasscode(e.target.value.replace(/\D/g, ''))}
              placeholder="Snowflake MFA"
              className="w-28 rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs dark:border-slate-700 dark:bg-slate-950"
            />
          )}
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800/60 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <div className="mb-6 whitespace-pre-wrap rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-200">
          {Object.entries(data.errors).map(([k, v]) => `${k}: ${v}`).join('\n')}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
        </div>
      ) : (
        <>
          {summary && (
            <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                  ${summary.current_open_pipeline.toLocaleString()}
                </p>
                <p className="text-xs text-slate-500">Open pipeline ({summary.current_open_deals} deals)</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <p className="text-2xl font-bold text-slate-900 dark:text-slate-50">
                  ${summary.ytd_won_revenue.toLocaleString()}
                </p>
                <p className="text-xs text-slate-500">YTD won revenue</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <p className="text-2xl font-bold text-slate-900 dark:text-slate-50">{summary.ytd_new_contacts}</p>
                <p className="text-xs text-slate-500">YTD new leads</p>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/40 dark:bg-amber-950/20">
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{summary.inactive_patients}</p>
                <p className="text-xs text-slate-500">Lapsed patients (revenue risk)</p>
              </div>
            </div>
          )}

          <section className="mb-8">
            <h2 className="mb-4 text-sm font-semibold text-slate-800 dark:text-slate-200">
              This month&apos;s decision factors
              {summary?.current_month && (
                <span className="ml-2 font-normal text-slate-500">({summary.current_month})</span>
              )}
            </h2>
            <RevenueFactorCards factors={data?.current_month_factors || []} />
          </section>

          <section>
            <h2 className="mb-4 text-sm font-semibold text-slate-800 dark:text-slate-200">
              Monthly revenue history
            </h2>
            {data?.message && !data.monthly?.length ? (
              <p className="text-sm text-slate-500">{data.message}</p>
            ) : (
              <MonthlyRevenueTable monthly={data?.monthly || []} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
