'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Mail, Phone, Send, Tag, UserCheck } from 'lucide-react';
import DataToolbar from '@/components/ui/DataToolbar';
import EmptyState from '@/components/ui/EmptyState';
import LoadMoreSentinel from '@/components/ui/LoadMoreSentinel';
import PageShell, { AlertBanner, MfaInput, RefreshButton } from '@/components/ui/PageShell';
import Pagination from '@/components/ui/Pagination';
import { CardGridSkeleton, ListSkeleton, PageHeaderSkeleton } from '@/components/ui/Skeleton';
import { useConfirm } from '@/components/providers/ConfirmProvider';
import { useToast } from '@/components/providers/ToastProvider';
import { useDebounce, usePagination } from '@/hooks/useEnterprise';
import { apiFetch, getToken } from '@/lib/api';
import { downloadAuthenticatedExport, exportToCsv, exportToExcel } from '@/lib/export';
import type { PaginatedMeta } from '@/lib/types/common';

interface ReactivateCandidate {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  source: string;
  days_inactive?: number | null;
  channel: string;
  discount_offer?: string;
  discount_code?: string;
  discount_percent?: number;
  call_script?: string;
}

interface ReactivateSettings {
  inactive_days: number;
  discount_percent: number;
  discount_code: string;
  discount_label: string;
  subject_template: string;
  body_template: string;
  provider: 'ghl' | 'smtp';
  enabled: boolean;
}

interface ReactivateResponse {
  settings?: ReactivateSettings;
  summary?: {
    total_candidates: number;
    email_ready: number;
    manual_followup: number;
    discount_offer: string;
  };
  candidates?: {
    email_ready: ReactivateCandidate[];
    manual_only: ReactivateCandidate[];
    total: number;
  };
  pagination?: PaginatedMeta;
  connected_sources?: Record<string, boolean>;
  generated_at?: string;
  message?: string;
}

const DEFAULT_SETTINGS: ReactivateSettings = {
  inactive_days: 90,
  discount_percent: 15,
  discount_code: 'COMEBACK15',
  discount_label: '15% off your next visit',
  subject_template: "We miss you, {{first_name}} — {{discount}} on your next visit",
  body_template: `<p>Hi {{name}},</p>
<p>It's been a while since your last visit. Enjoy <strong>{{discount}}</strong> with code <strong>{{discount_code}}</strong>.</p>`,
  provider: 'ghl',
  enabled: true,
};

const EXPORT_COLUMNS = [
  { key: 'name', header: 'Name' },
  { key: 'phone', header: 'Phone' },
  { key: 'email', header: 'Email' },
  { key: 'source', header: 'Source' },
  { key: 'days_inactive', header: 'Days Inactive' },
  { key: 'discount_offer', header: 'Discount Offer' },
  { key: 'discount_code', header: 'Discount Code' },
];

export default function ReactivateCampaignPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { confirm } = useConfirm();
  const { page, pageSize, setPage, setPageSize, reset } = usePagination(1, 25);

  const [data, setData] = useState<ReactivateResponse | null>(null);
  const [settings, setSettings] = useState<ReactivateSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');
  const [search, setSearch] = useState('');
  const [channel, setChannel] = useState<'all' | 'email' | 'manual'>('all');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [manualAccumulated, setManualAccumulated] = useState<ReactivateCandidate[]>([]);
  const [manualPage, setManualPage] = useState(1);
  const [manualLoadingMore, setManualLoadingMore] = useState(false);

  const debouncedSearch = useDebounce(search, 300);

  const loadCampaign = useCallback(
    async (opts?: { passcode?: string; pageOverride?: number; appendManual?: boolean }) => {
      setError(null);
      const currentPage = opts?.pageOverride ?? page;
      try {
        const params = new URLSearchParams({
          limit_per_entity: '500',
          page: String(opts?.appendManual ? manualPage + 1 : currentPage),
          page_size: String(pageSize),
          channel: opts?.appendManual ? 'manual' : channel,
          sort: '-days_inactive',
        });
        if (debouncedSearch.trim()) params.set('q', debouncedSearch.trim());
        if (opts?.passcode?.trim()) params.set('snowflake_passcode', opts.passcode.trim());

        const res = await apiFetch(`/api/reactivate/campaign?${params.toString()}`, {}, 120_000);
        const json: ReactivateResponse = await res.json();
        if (!res.ok) throw new Error((json as { message?: string }).message || 'Failed to load campaign');

        if (opts?.appendManual) {
          setManualAccumulated((prev) => [...prev, ...(json.candidates?.manual_only || [])]);
          setManualPage((p) => p + 1);
        } else {
          setData(json);
          if (json.settings) setSettings({ ...DEFAULT_SETTINGS, ...json.settings });
          setManualAccumulated(json.candidates?.manual_only || []);
          setManualPage(currentPage);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load campaign');
      }
    },
    [page, pageSize, debouncedSearch, channel, manualPage],
  );

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    reset();
    loadCampaign().finally(() => setLoading(false));
  }, [router, debouncedSearch, channel, page, pageSize, reset, loadCampaign]);

  const refresh = async () => {
    setRefreshing(true);
    reset();
    await loadCampaign({ passcode: snowflakePasscode });
    setSnowflakePasscode('');
    setRefreshing(false);
    toast('Campaign data refreshed', { variant: 'success' });
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      const res = await apiFetch('/api/reactivate/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Failed to save');
      setSettings({ ...settings, ...json });
      toast('Campaign settings saved', { variant: 'success' });
      await loadCampaign({ passcode: snowflakePasscode });
    } catch (e) {
      toast('Save failed', { description: e instanceof Error ? e.message : undefined, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const sendEmails = async (dryRun: boolean, sendAll: boolean) => {
    if (!dryRun) {
      const ok = await confirm({
        title: sendAll ? 'Send reactivation emails to all?' : `Send to ${selected.size} selected?`,
        description: `Discount code ${settings.discount_code} (${settings.discount_percent}% off) will be included.`,
        confirmLabel: 'Send emails',
        variant: 'default',
      });
      if (!ok) return;
    }

    setSending(true);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500' });
      if (snowflakePasscode.trim()) params.set('snowflake_passcode', snowflakePasscode.trim());
      const res = await apiFetch(
        `/api/reactivate/send?${params.toString()}`,
        {
          method: 'POST',
          body: JSON.stringify({
            send_all: sendAll,
            dry_run: dryRun,
            contact_ids: sendAll ? undefined : Array.from(selected),
          }),
        },
        120_000,
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Send failed');
      toast(
        dryRun ? `Dry run: ${json.sent} email(s)` : `Sent ${json.sent} email(s)`,
        { variant: 'success', description: `Code: ${json.discount_code}` },
      );
    } catch (e) {
      toast('Send failed', { description: e instanceof Error ? e.message : undefined, variant: 'error' });
    } finally {
      setSending(false);
    }
  };

  const exportList = async (format: 'csv' | 'excel' | 'server') => {
    try {
      if (format === 'server') {
        await downloadAuthenticatedExport(
          `/api/reactivate/export?scope=all&limit_per_entity=500`,
          'reactivate-campaign-all.csv',
          getToken(),
        );
        toast('Export downloaded', { variant: 'success' });
        return;
      }
      const rows = [...emailReady, ...manualList];
      if (format === 'csv') exportToCsv(rows, EXPORT_COLUMNS, 'reactivate-campaign');
      else exportToExcel(rows, EXPORT_COLUMNS, 'reactivate-campaign');
      toast(`Exported ${rows.length} rows`, { variant: 'success' });
    } catch (e) {
      toast('Export failed', { description: e instanceof Error ? e.message : undefined, variant: 'error' });
    }
  };

  const emailReady = data?.candidates?.email_ready || [];
  const manualList = channel === 'manual' ? manualAccumulated : data?.candidates?.manual_only || [];
  const summary = data?.summary;
  const connected = data?.connected_sources || {};
  const pagination = data?.pagination;
  const manualHasMore = pagination?.has_next && channel === 'manual';

  const inputClass =
    'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950';

  if (loading && !data) {
    return (
      <PageShell title="Reactivate Campaign" eyebrow="Win-back" eyebrowIcon={UserCheck}>
        <PageHeaderSkeleton />
        <CardGridSkeleton />
        <ListSkeleton rows={6} />
      </PageShell>
    );
  }

  return (
    <PageShell
      eyebrow="Win-back"
      eyebrowIcon={UserCheck}
      title="Reactivate Campaign"
      printTitle="Reactivate Campaign — 90+ Day No-Show Patients"
      description={
        <>
          Identify patients with {settings.inactive_days}+ days no show, offer discounts, and reach out via email or
          manual follow-up.
          {data?.generated_at && (
            <span className="text-slate-500"> · Updated {new Date(data.generated_at).toLocaleString()}</span>
          )}
        </>
      }
      actions={
        <>
          {connected.snowflake && <MfaInput value={snowflakePasscode} onChange={setSnowflakePasscode} />}
          <RefreshButton onClick={refresh} loading={refreshing} />
        </>
      }
    >
      {error && <AlertBanner variant="error">{error}</AlertBanner>}

      {summary && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4" data-print-hide>
          {[
            { label: 'Total at risk', value: summary.total_candidates },
            { label: 'Email outreach', value: summary.email_ready },
            { label: 'Manual follow-up', value: summary.manual_followup },
            { label: 'Discount', value: summary.discount_offer, small: true },
          ].map(({ label, value, small }) => (
            <div
              key={label}
              className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900/50"
            >
              <p className={`font-bold text-slate-900 dark:text-slate-50 ${small ? 'text-sm' : 'text-2xl'}`}>
                {value}
              </p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>
      )}

      <section className="mb-8 rounded-2xl border border-rose-200 bg-rose-50/40 p-5 dark:border-rose-800/40 dark:bg-rose-950/20" data-print-hide>
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <Tag className="h-4 w-4 text-rose-500" aria-hidden />
          Discount &amp; email template
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs text-slate-500">No-show threshold (days)</label>
            <input type="number" min={30} max={365} value={settings.inactive_days}
              onChange={(e) => setSettings((s) => ({ ...s, inactive_days: Number(e.target.value) }))}
              className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Discount %</label>
            <input type="number" min={5} max={50} value={settings.discount_percent}
              onChange={(e) => setSettings((s) => ({ ...s, discount_percent: Number(e.target.value) }))}
              className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Promo code</label>
            <input value={settings.discount_code}
              onChange={(e) => setSettings((s) => ({ ...s, discount_code: e.target.value.toUpperCase() }))}
              className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Discount label</label>
            <input value={settings.discount_label}
              onChange={(e) => setSettings((s) => ({ ...s, discount_label: e.target.value }))}
              className={inputClass} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={saveSettings} disabled={saving}
            className="rounded-lg bg-rose-600 px-4 py-2 text-sm text-white hover:bg-rose-500 disabled:opacity-50">
            {saving ? 'Saving…' : 'Save settings'}
          </button>
        </div>
      </section>

      <DataToolbar
        searchValue={search}
        onSearchChange={(v) => { setSearch(v); reset(); }}
        searchPlaceholder="Filter by name, email, phone, source…"
        onExportCsv={() => exportList('csv')}
        onExportExcel={() => exportList('excel')}
        onPrint={() => window.print()}
        extra={
          <select
            value={channel}
            onChange={(e) => { setChannel(e.target.value as 'all' | 'email' | 'manual'); reset(); }}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs dark:border-slate-700 dark:bg-slate-950"
            aria-label="Filter by channel"
          >
            <option value="all">All channels</option>
            <option value="email">Email only</option>
            <option value="manual">Manual only</option>
          </select>
        }
      />

      {!summary?.total_candidates ? (
        <EmptyState
          title="No reactivation candidates"
          description={data?.message ?? 'Connect data sources and refresh to find 90+ day no-show patients.'}
        />
      ) : (
        <>
          {(channel === 'all' || channel === 'email') && (
            <section className="mb-8">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold">
                  <Mail className="h-4 w-4" aria-hidden />
                  Email outreach ({summary.email_ready})
                </h2>
                <div className="flex flex-wrap gap-2" data-print-hide>
                  <button type="button" disabled={sending || !emailReady.length}
                    onClick={() => sendEmails(true, true)}
                    className="rounded-lg border px-3 py-1.5 text-xs disabled:opacity-50">Dry run</button>
                  <button type="button" disabled={sending || !emailReady.length}
                    onClick={() => sendEmails(false, true)}
                    className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white disabled:opacity-50">
                    <Send className="h-3 w-3" /> Send all
                  </button>
                </div>
              </div>
              <div className="space-y-2 rounded-xl border border-slate-200 dark:border-slate-800">
                {emailReady.map((c) => (
                  <label key={c.id} className="flex cursor-pointer items-center gap-3 border-b px-4 py-3 last:border-0 dark:border-slate-800">
                    <input type="checkbox" checked={selected.has(c.id)} onChange={() => {
                      setSelected((prev) => { const n = new Set(prev); n.has(c.id) ? n.delete(c.id) : n.add(c.id); return n; });
                    }} className="h-4 w-4 accent-indigo-600" data-print-hide />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{c.name}</p>
                      <p className="text-xs text-slate-500">{c.email} · {c.days_inactive ?? '?'}d · {c.discount_offer}</p>
                    </div>
                  </label>
                ))}
              </div>
            </section>
          )}

          {(channel === 'all' || channel === 'manual') && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <Phone className="h-4 w-4" aria-hidden />
                Manual follow-up ({summary.manual_followup})
              </h2>
              <div className="space-y-3">
                {manualList.map((c) => (
                  <div key={c.id} className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-800/40 dark:bg-amber-950/20">
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-slate-500">{c.phone || 'No phone'} · {c.days_inactive ?? '?'}d inactive · {c.discount_code}</p>
                    {c.call_script && <p className="mt-2 text-xs italic text-slate-600 dark:text-slate-400">&ldquo;{c.call_script}&rdquo;</p>}
                  </div>
                ))}
              </div>
              {channel === 'manual' && (
                <LoadMoreSentinel
                  hasMore={!!manualHasMore}
                  loading={manualLoadingMore}
                  onLoadMore={async () => {
                    setManualLoadingMore(true);
                    await loadCampaign({ appendManual: true });
                    setManualLoadingMore(false);
                  }}
                />
              )}
            </section>
          )}

          {pagination && channel !== 'manual' && (
            <Pagination
              className="mt-6"
              meta={pagination}
              onPageChange={setPage}
              onPageSizeChange={(size) => { setPageSize(size); reset(); }}
            />
          )}
        </>
      )}
    </PageShell>
  );
}
