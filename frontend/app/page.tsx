'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  BarChart3,
  Users,
  MessageSquare,
  AlertCircle,
} from 'lucide-react';
import KpiCard, { KpiData } from '@/components/dashboard/KpiCard';
import { apiFetch, getToken } from '@/lib/api';
import PageShell, { AlertBanner, MfaInput, RefreshButton } from '@/components/ui/PageShell';
import Badge from '@/components/ui/Badge';
import { Card, CardHeader } from '@/components/ui/Card';
import EmptyState from '@/components/ui/EmptyState';
import { CardGridSkeleton } from '@/components/ui/Skeleton';

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

  const description = (
    <>
      KPI cards from connected GoHighLevel and Snowflake data sources.
      {insights?.generated_at && (
        <span className="text-fg-subtle">
          {' '}
          · Updated {new Date(insights.generated_at).toLocaleString()}
        </span>
      )}
    </>
  );

  return (
    <PageShell
      eyebrow="Marketing Intelligence"
      eyebrowIcon={BarChart3}
      title="Insights Dashboard"
      description={description}
      width="full"
      actions={
        <>
          {connected.snowflake && (
            <MfaInput value={snowflakePasscode} onChange={setSnowflakePasscode} />
          )}
          <RefreshButton onClick={refresh} loading={refreshing || loading} label="Refresh insights" />
        </>
      }
    >
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <span className="text-caption">Connected:</span>
        {connectedNames.length > 0 ? (
          connectedNames.map((name) => (
            <Badge key={name} variant="success">
              {name}
            </Badge>
          ))
        ) : (
          <span className="text-caption text-warning">
            None — hover the bottom bar to open DB Connectors
          </span>
        )}
      </div>

      {error && <AlertBanner variant="error">{error}</AlertBanner>}

      {insights?.errors && Object.keys(insights.errors).length > 0 && (
        <AlertBanner variant="warning">
          <pre className="whitespace-pre-wrap font-sans text-xs">
            {Object.entries(insights.errors)
              .map(([k, v]) => `${k}: ${v}`)
              .join('\n')}
          </pre>
        </AlertBanner>
      )}

      {loading ? (
        <CardGridSkeleton count={6} />
      ) : insights?.message && !insights.kpis?.length ? (
        <EmptyState title="No insights yet" description={insights.message} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
            {(insights?.kpis || []).map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2" padding="md">
              <CardHeader
                title="Source breakdown"
                description="Entity counts by connected data source"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                {insights?.summary?.ghl && (
                  <div className="rounded-lg border border-primary/20 bg-primary-subtle/50 p-4">
                    <p className="mb-3 text-caption font-medium uppercase tracking-wide text-primary">
                      GoHighLevel
                    </p>
                    <ul className="space-y-2 text-sm text-fg-muted">
                      <li className="flex justify-between">
                        <span>Contacts</span>
                        <span className="font-medium text-fg">{insights.summary.ghl.contacts}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Opportunities</span>
                        <span className="font-medium text-fg">{insights.summary.ghl.opportunities}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Conversations</span>
                        <span className="font-medium text-fg">{insights.summary.ghl.conversations}</span>
                      </li>
                      <li className="flex justify-between text-warning">
                        <span>90d no follow-up</span>
                        <span className="font-medium">{insights.summary.ghl.inactive_no_followup}</span>
                      </li>
                    </ul>
                  </div>
                )}
                {insights?.summary?.snowflake && (
                  <div className="rounded-lg border border-info/20 bg-info-subtle/50 p-4">
                    <p className="mb-3 text-caption font-medium uppercase tracking-wide text-info">
                      Snowflake
                    </p>
                    <ul className="space-y-2 text-sm text-fg-muted">
                      <li className="flex justify-between">
                        <span>Contacts</span>
                        <span className="font-medium text-fg">{insights.summary.snowflake.contacts}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Opportunities</span>
                        <span className="font-medium text-fg">{insights.summary.snowflake.opportunities}</span>
                      </li>
                      <li className="flex justify-between">
                        <span>Conversations</span>
                        <span className="font-medium text-fg">{insights.summary.snowflake.conversations}</span>
                      </li>
                      <li className="flex justify-between text-warning">
                        <span>90d stale</span>
                        <span className="font-medium">{insights.summary.snowflake.inactive_no_followup}</span>
                      </li>
                    </ul>
                  </div>
                )}
              </div>
            </Card>

            <Card accent="warning" padding="md">
              <CardHeader title="Re-engagement queue" />
              <p className="flex items-center gap-2 text-3xl font-semibold text-warning">
                <AlertCircle className="h-6 w-6" aria-hidden />
                {insights?.followup_candidate_count ?? 0}
              </p>
              <p className="mt-2 text-caption leading-relaxed">
                Customers with 90+ days no show and no follow-up. Open the bottom
                taskbar → Email Follow-up to configure and send campaigns.
              </p>
              <div className="mt-4 space-y-2 text-caption text-fg-muted">
                <p className="flex items-center gap-2">
                  <Users className="h-3.5 w-3.5" aria-hidden />
                  Hover bottom edge for settings
                </p>
                <p className="flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5" aria-hidden />
                  GHL or SMTP email delivery
                </p>
                <p className="flex items-center gap-2 text-success">
                  Open Compliance in bottom taskbar for service audit
                </p>
              </div>
            </Card>
          </div>
        </>
      )}
    </PageShell>
  );
}
