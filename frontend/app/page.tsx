'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  BarChart3,
  Loader2,
  RefreshCw,
  Users,
  TrendingUp,
  MessageSquare,
  AlertCircle,
} from 'lucide-react';
import KpiCard, { KpiData } from '@/components/dashboard/KpiCard';
import { apiFetch, getToken } from '@/lib/api';

interface InsightsResponse {
  kpis: KpiData[];
  followup_candidate_count?: number;
  connected_sources?: Record<string, boolean>;
  summary?: {
    ghl?: Record<string, number>;
    snowflake?: Record<string, number>;
  };
  errors?: Record<string, string>;
  message?: string;
  generated_at?: string;
}

const SOURCE_LABELS: Record<string, string> = {
  snowflake: 'Snowflake',
  ghl: 'GoHighLevel',
};

export default function DashboardPage() {
  const router = useRouter();
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const loadInsights = useCallback(async (passcode?: string) => {
    setError(null);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500', inactive_days: '90' });
      if (passcode?.trim()) {
        params.set('snowflake_passcode', passcode.trim());
      }
      const res = await apiFetch(`/api/insights?${params.toString()}`, {}, 120_000);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to load insights');
      }
      setInsights(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load insights');
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    loadInsights().finally(() => setLoading(false));
  }, [router, loadInsights]);

  const refresh = async () => {
    setRefreshing(true);
    await loadInsights(snowflakePasscode);
    setSnowflakePasscode('');
    setRefreshing(false);
  };

  const connected = insights?.connected_sources || {};
  const connectedNames = Object.entries(connected)
    .filter(([, v]) => v)
    .map(([k]) => SOURCE_LABELS[k] || k);

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-indigo-400">
            <BarChart3 className="h-5 w-5" />
            <span className="text-xs font-medium uppercase tracking-wider">
              Marketing Intelligence
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-50">Insights Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            KPI cards from connected GoHighLevel and Snowflake data sources.
            {insights?.generated_at && (
              <span className="text-slate-500">
                {' '}
                · Updated {new Date(insights.generated_at).toLocaleString()}
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
              className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs"
            />
          )}
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh insights
          </button>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <span className="text-xs text-slate-500">Connected:</span>
        {connectedNames.length > 0 ? (
          connectedNames.map((name) => (
            <span
              key={name}
              className="rounded-full border border-emerald-700/50 bg-emerald-900/30 px-2.5 py-0.5 text-xs text-emerald-300"
            >
              {name}
            </span>
          ))
        ) : (
          <span className="text-xs text-amber-400">
            None — hover the bottom bar to open DB Connectors
          </span>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {insights?.errors && Object.keys(insights.errors).length > 0 && (
        <div className="mb-6 whitespace-pre-wrap rounded-xl border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-xs text-amber-200">
          {Object.entries(insights.errors)
            .map(([k, v]) => `${k}: ${v}`)
            .join('\n')}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
        </div>
      ) : insights?.message && !insights.kpis?.length ? (
        <div className="rounded-2xl border border-dashed border-slate-800 px-6 py-16 text-center text-slate-500">
          {insights.message}
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {(insights?.kpis || []).map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 lg:col-span-2">
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-200">
                <TrendingUp className="h-4 w-4 text-indigo-400" />
                Source breakdown
              </h2>
              <div className="grid gap-4 sm:grid-cols-2">
                {insights?.summary?.ghl && (
                  <div className="rounded-xl border border-violet-800/30 bg-violet-950/20 p-4">
                    <p className="mb-3 text-xs font-medium uppercase tracking-wide text-violet-300">
                      GoHighLevel
                    </p>
                    <ul className="space-y-2 text-sm text-slate-300">
                      <li className="flex justify-between">
                        <span>Contacts</span>
                        <span>{insights.summary.ghl.contacts}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Opportunities</span>
                        <span>{insights.summary.ghl.opportunities}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Conversations</span>
                        <span>{insights.summary.ghl.conversations}</span>
                      </li>
                      <li className="flex justify-between text-amber-300">
                        <span>90d no follow-up</span>
                        <span>{insights.summary.ghl.inactive_no_followup}</span>
                      </li>
                    </ul>
                  </div>
                )}
                {insights?.summary?.snowflake && (
                  <div className="rounded-xl border border-sky-800/30 bg-sky-950/20 p-4">
                    <p className="mb-3 text-xs font-medium uppercase tracking-wide text-sky-300">
                      Snowflake
                    </p>
                    <ul className="space-y-2 text-sm text-slate-300">
                      <li className="flex justify-between">
                        <span>Contacts</span>
                        <span>{insights.summary.snowflake.contacts}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Opportunities</span>
                        <span>{insights.summary.snowflake.opportunities}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Conversations</span>
                        <span>{insights.summary.snowflake.conversations}</span>
                      </li>
                      <li className="flex justify-between text-amber-300">
                        <span>90d stale</span>
                        <span>{insights.summary.snowflake.inactive_no_followup}</span>
                      </li>
                    </ul>
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-amber-800/40 bg-amber-950/20 p-5">
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-200">
                <AlertCircle className="h-4 w-4" />
                Re-engagement queue
              </h2>
              <p className="text-3xl font-bold text-amber-100">
                {insights?.followup_candidate_count ?? 0}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-amber-300/80">
                Customers with 90+ days no show and no follow-up. Open the bottom
                taskbar → Email Follow-up to configure and send campaigns.
              </p>
              <div className="mt-4 space-y-2 text-xs text-slate-400">
                <p className="flex items-center gap-2">
                  <Users className="h-3.5 w-3.5" />
                  Hover bottom edge for settings
                </p>
                <p className="flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5" />
                  GHL or SMTP email delivery
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
