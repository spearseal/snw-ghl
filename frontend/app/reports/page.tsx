'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  Printer,
} from 'lucide-react';
import PageShell, { AlertBanner, MfaInput, RefreshButton } from '@/components/ui/PageShell';
import EmptyState from '@/components/ui/EmptyState';
import { CardGridSkeleton, PageHeaderSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/providers/ToastProvider';
import { apiFetch, getToken } from '@/lib/api';
import { exportToCsv, exportToExcel } from '@/lib/export';
import { cn } from '@/lib/cn';

interface ReportMetric {
  label: string;
  value: string | number;
  detail?: string;
}

interface ReportSection {
  id: string;
  title: string;
  description: string;
  category: string;
  metrics: ReportMetric[];
  highlights?: string[];
  rows?: Record<string, unknown>[];
}

interface ReportsResponse {
  reports?: ReportSection[];
  source_label?: string;
  connected_sources?: Record<string, boolean>;
  generated_at?: string;
  message?: string;
  errors?: Record<string, string>;
}

const CATEGORY_STYLES: Record<string, string> = {
  operations: 'border-indigo-200 bg-indigo-50/50 dark:border-indigo-800/40 dark:bg-indigo-950/20',
  finance: 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/40 dark:bg-emerald-950/20',
  clinical: 'border-sky-200 bg-sky-50/50 dark:border-sky-800/40 dark:bg-sky-950/20',
  compliance: 'border-amber-200 bg-amber-50/50 dark:border-amber-800/40 dark:bg-amber-950/20',
  leadership: 'border-violet-200 bg-violet-50/50 dark:border-violet-800/40 dark:bg-violet-950/20',
};

function rowsToColumns(rows: Record<string, unknown>[]) {
  if (!rows.length) return [];
  return Object.keys(rows[0]).map((key) => ({
    key,
    header: key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
  }));
}

export default function ReportsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['executive']));

  const loadReports = useCallback(async (passcode?: string) => {
    setError(null);
    try {
      const params = new URLSearchParams({ limit_per_entity: '500', inactive_days: '90' });
      if (passcode?.trim()) params.set('snowflake_passcode', passcode.trim());
      const res = await apiFetch(`/api/reports?${params.toString()}`, {}, 120_000);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || json.message || 'Failed to load reports');
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load reports');
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    setLoading(true);
    loadReports().finally(() => setLoading(false));
  }, [router, loadReports]);

  const refresh = async () => {
    setRefreshing(true);
    await loadReports(snowflakePasscode);
    setSnowflakePasscode('');
    setRefreshing(false);
    toast('Reports refreshed', { variant: 'success' });
  };

  const toggleExpand = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const exportReport = (report: ReportSection, format: 'csv' | 'excel') => {
    const rows = report.rows?.length
      ? report.rows
      : report.metrics.map((m) => ({
          label: m.label,
          value: m.value,
          detail: m.detail ?? '',
        }));
    const columns = rowsToColumns(rows as Record<string, unknown>[]);
    const slug = report.id.replace(/[^a-z0-9]+/gi, '-');
    if (format === 'csv') exportToCsv(rows as Record<string, unknown>[], columns, `report-${slug}`);
    else exportToExcel(rows as Record<string, unknown>[], columns, `report-${slug}`);
    toast(`Exported ${report.title}`, { variant: 'success' });
  };

  const connected = data?.connected_sources || {};
  const reports = data?.reports || [];

  if (loading && !data) {
    return (
      <PageShell title="Reports" eyebrow="Analytics" eyebrowIcon={FileText}>
        <PageHeaderSkeleton />
        <CardGridSkeleton count={3} />
      </PageShell>
    );
  }

  return (
    <PageShell
      eyebrow="Analytics"
      eyebrowIcon={FileText}
      title="Reports"
      printTitle="Business Reports"
      description={
        <>
          Executive, revenue, retention, treatment, compliance, and CEO reports from connected data.
          {data?.source_label && <span className="text-slate-500"> · {data.source_label}</span>}
          {data?.generated_at && (
            <span className="text-slate-500">
              {' '}
              · Generated {new Date(data.generated_at).toLocaleString()}
            </span>
          )}
        </>
      }
      actions={
        <>
          {connected.snowflake && <MfaInput value={snowflakePasscode} onChange={setSnowflakePasscode} />}
          <RefreshButton onClick={refresh} loading={refreshing} label="Refresh reports" />
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
            data-print-hide
          >
            <Printer className="h-4 w-4" aria-hidden />
            Print all
          </button>
        </>
      }
    >
      {error && <AlertBanner variant="error">{error}</AlertBanner>}

      {data?.errors && Object.keys(data.errors).length > 0 && (
        <AlertBanner variant="warning">
          {Object.entries(data.errors).map(([k, v]) => `${k}: ${v}`).join(' · ')}
        </AlertBanner>
      )}

      {!reports.length ? (
        <EmptyState
          title="No reports available"
          description={data?.message ?? 'Connect GoHighLevel and/or Snowflake to generate reports.'}
        />
      ) : (
        <div className="space-y-4">
          {reports.map((report) => {
            const isOpen = expanded.has(report.id);
            const style = CATEGORY_STYLES[report.category] || CATEGORY_STYLES.operations;

            return (
              <article
                key={report.id}
                className={cn('overflow-hidden rounded-2xl border', style)}
              >
                <button
                  type="button"
                  onClick={() => toggleExpand(report.id)}
                  className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left"
                  aria-expanded={isOpen}
                >
                  <div className="min-w-0">
                    <h2 className="font-semibold text-slate-900 dark:text-slate-100">{report.title}</h2>
                    <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{report.description}</p>
                  </div>
                  {isOpen ? (
                    <ChevronDown className="h-5 w-5 shrink-0 text-slate-400" aria-hidden />
                  ) : (
                    <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" aria-hidden />
                  )}
                </button>

                <div className="grid grid-cols-2 gap-3 border-t border-inherit px-5 py-4 sm:grid-cols-4">
                  {report.metrics.map((m) => (
                    <div key={m.label}>
                      <p className="text-lg font-bold text-slate-900 dark:text-slate-50">{m.value}</p>
                      <p className="text-xs text-slate-500">{m.label}</p>
                    </div>
                  ))}
                </div>

                {isOpen && (
                  <div className="border-t border-inherit px-5 py-4">
                    {report.highlights && report.highlights.length > 0 && (
                      <ul className="mb-4 space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        {report.highlights.map((h, i) => (
                          <li key={i}>· {h}</li>
                        ))}
                      </ul>
                    )}

                    {report.rows && report.rows.length > 0 && (
                      <div className="mb-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-slate-100 text-xs uppercase text-slate-500 dark:bg-slate-900">
                            <tr>
                              {Object.keys(report.rows[0]).map((col) => (
                                <th key={col} className="px-4 py-2">
                                  {col.replace(/_/g, ' ')}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {report.rows.map((row, i) => (
                              <tr key={i} className="border-t border-slate-200 dark:border-slate-800">
                                {Object.values(row).map((val, j) => (
                                  <td key={j} className="px-4 py-2 text-slate-700 dark:text-slate-300">
                                    {String(val ?? '')}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2" data-print-hide>
                      <button
                        type="button"
                        onClick={() => exportReport(report, 'csv')}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-white/60 dark:border-slate-600"
                      >
                        <FileText className="h-3.5 w-3.5" aria-hidden />
                        Export CSV
                      </button>
                      <button
                        type="button"
                        onClick={() => exportReport(report, 'excel')}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-white/60 dark:border-slate-600"
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden />
                        Export Excel
                      </button>
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
