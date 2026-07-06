'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { HeartPulse, Loader2, RefreshCw } from 'lucide-react';
import HealthIntakeForm from '@/components/treatment/HealthIntakeForm';
import TreatmentPlanList, { TreatmentPlan } from '@/components/treatment/TreatmentPlanList';
import { apiFetch, getToken } from '@/lib/api';

interface TreatmentPlansResponse {
  plans?: TreatmentPlan[];
  summary?: {
    total_patients: number;
    pending_intake: number;
    active_treatment: number;
    re_engagement: number;
    intakes_on_file: number;
  };
  connected_sources?: Record<string, boolean>;
  errors?: Record<string, string>;
  message?: string;
  generated_at?: string;
}

export default function TreatmentPlansPage() {
  const router = useRouter();
  const [data, setData] = useState<TreatmentPlansResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const loadPlans = useCallback(async (passcode?: string) => {
    setError(null);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500', inactive_days: '90', limit: '50' });
      if (passcode?.trim()) {
        params.set('snowflake_passcode', passcode.trim());
      }
      const res = await apiFetch(`/api/treatment-plans?${params.toString()}`, {}, 120_000);
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.detail || json.message || 'Failed to load treatment plans');
      }
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load treatment plans');
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    loadPlans().finally(() => setLoading(false));
  }, [router, loadPlans]);

  const refresh = async () => {
    setRefreshing(true);
    await loadPlans(snowflakePasscode);
    setSnowflakePasscode('');
    setRefreshing(false);
  };

  const onIntakeSubmitted = async () => {
    await loadPlans(snowflakePasscode);
  };

  const summary = data?.summary;
  const connected = data?.connected_sources || {};

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-emerald-500 dark:text-emerald-400">
            <HeartPulse className="h-5 w-5" />
            <span className="text-xs font-medium uppercase tracking-wider">Patient Care</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Treatment Plans</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Personalized plans per patient from Snowflake data and health intake forms.
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
            Refresh plans
          </button>
        </div>
      </div>

      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Patients', value: summary.total_patients },
            { label: 'Pending intake', value: summary.pending_intake },
            { label: 'Active treatment', value: summary.active_treatment },
            { label: 'Re-engagement', value: summary.re_engagement },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/50"
            >
              <p className="text-2xl font-bold text-slate-900 dark:text-slate-50">{value}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>
      )}

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

      <div className="mb-8">
        <HealthIntakeForm onSubmitted={onIntakeSubmitted} snowflakePasscode={snowflakePasscode} />
      </div>

      {loading ? (
        <div className="flex justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
        </div>
      ) : data?.message && !data.plans?.length ? (
        <div className="rounded-2xl border border-dashed border-slate-200 px-6 py-16 text-center text-slate-500 dark:border-slate-800">
          {data.message}
        </div>
      ) : (
        <TreatmentPlanList plans={data?.plans || []} />
      )}
    </div>
  );
}
