'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ClipboardList, Loader2, RefreshCw } from 'lucide-react';
import CeoTaskList, { CeoTask } from '@/components/dashboard/CeoTaskList';
import { apiFetch, getToken } from '@/lib/api';

const SOURCE_LABELS: Record<string, string> = {
  snowflake: 'Snowflake',
  ghl: 'GoHighLevel',
};

interface CeoTasksResponse {
  ceo_tasks?: CeoTask[];
  connected_sources?: Record<string, boolean>;
  errors?: Record<string, string>;
  message?: string;
  generated_at?: string;
}

export default function CeoTasksPage() {
  const router = useRouter();
  const [data, setData] = useState<CeoTasksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const loadTasks = useCallback(async (passcode?: string) => {
    setError(null);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500', inactive_days: '90' });
      if (passcode?.trim()) {
        params.set('snowflake_passcode', passcode.trim());
      }
      const res = await apiFetch(`/api/insights?${params.toString()}`, {}, 120_000);
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.detail || json.message || 'Failed to load CEO tasks');
      }
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load CEO tasks');
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    loadTasks().finally(() => setLoading(false));
  }, [router, loadTasks]);

  const refresh = async () => {
    setRefreshing(true);
    await loadTasks(snowflakePasscode);
    setSnowflakePasscode('');
    setRefreshing(false);
  };

  const connected = data?.connected_sources || {};
  const connectedNames = Object.entries(connected)
    .filter(([, v]) => v)
    .map(([k]) => SOURCE_LABELS[k] || k);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-violet-400">
            <ClipboardList className="h-5 w-5" />
            <span className="text-xs font-medium uppercase tracking-wider">
              CEO Priorities
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Top 5 Tasks for Medspa CEOs</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Prioritized actions from your connected GoHighLevel and Snowflake patient data.
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
              className="w-28 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 font-mono text-xs"
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
            Refresh tasks
          </button>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        <span className="text-xs text-slate-500">Data sources:</span>
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
            None — open DB Connectors from the bottom taskbar
          </span>
        )}
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <div className="mb-6 whitespace-pre-wrap rounded-xl border border-amber-800/50 bg-amber-950/30 px-4 py-3 text-xs text-amber-200">
          {Object.entries(data.errors)
            .map(([k, v]) => `${k}: ${v}`)
            .join('\n')}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
        </div>
      ) : data?.message && !data.ceo_tasks?.length ? (
        <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 px-6 py-16 text-center text-slate-500">
          {data.message}
        </div>
      ) : (
        <div className="rounded-2xl border border-indigo-800/40 bg-gradient-to-br from-indigo-50 to-slate-100 p-6 dark:border-indigo-800/40 dark:from-indigo-950/40 dark:to-slate-900/60">
          <CeoTaskList tasks={data?.ceo_tasks || []} />
        </div>
      )}
    </div>
  );
}
