'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  UserPlus,
} from 'lucide-react';
import { apiFetch } from '@/lib/api';

interface Finding {
  severity: string;
  category: string;
  title: string;
  detail: string;
  count: number;
}

interface Recommendation {
  priority: string;
  action: string;
  reason: string;
  contact_id?: string;
  contact_name?: string;
  source?: string;
  suggested_channel?: string;
  conversation_id?: string;
}

interface ComplianceResponse {
  compliance_score: number;
  grade: string;
  summary: string;
  findings: Finding[];
  followup_recommendations: Recommendation[];
  recommendation_count?: number;
  errors?: Record<string, string>;
}

const SEVERITY_STYLES: Record<string, string> = {
  high: 'border-red-800/50 bg-red-950/30 text-red-300',
  medium: 'border-amber-800/50 bg-amber-950/30 text-amber-200',
  info: 'border-sky-800/50 bg-sky-950/30 text-sky-300',
};

const PRIORITY_STYLES: Record<string, string> = {
  high: 'text-red-400',
  medium: 'text-amber-400',
  low: 'text-slate-400',
};

export default function CompliancePanel() {
  const [data, setData] = useState<ComplianceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/compliance/evaluate', {}, 120_000);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || 'Compliance evaluation failed');
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
      </div>
    );
  }

  const score = data?.compliance_score ?? 0;
  const grade = data?.grade ?? 'N/A';
  const scoreColor =
    score >= 90 ? 'text-emerald-400' : score >= 75 ? 'text-sky-400' : score >= 60 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-emerald-900/30 p-3">
            <ShieldCheck className="h-6 w-6 text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-200">Customer service compliance</p>
            <p className="text-xs text-slate-500">
              Evaluates patient communication data and recommends follow-ups
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Re-evaluate
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-center">
          <p className={`text-4xl font-bold ${scoreColor}`}>{score}</p>
          <p className="text-xs text-slate-500">Compliance score</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-center">
          <p className="text-4xl font-bold text-indigo-300">{grade}</p>
          <p className="text-xs text-slate-500">Grade</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-center">
          <p className="text-4xl font-bold text-violet-300">
            {data?.recommendation_count ?? data?.followup_recommendations?.length ?? 0}
          </p>
          <p className="text-xs text-slate-500">Follow-up actions</p>
        </div>
      </div>

      {data?.summary && (
        <p className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3 text-sm text-slate-300">
          {data.summary}
        </p>
      )}

      {data?.findings && data.findings.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <AlertTriangle className="h-3.5 w-3.5" />
            Findings
          </h3>
          <div className="space-y-2">
            {data.findings.map((f, i) => (
              <div
                key={i}
                className={`rounded-lg border px-3 py-2.5 text-sm ${
                  SEVERITY_STYLES[f.severity] || SEVERITY_STYLES.info
                }`}
              >
                <p className="font-medium">{f.title}</p>
                <p className="mt-0.5 text-xs opacity-90">{f.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {data?.followup_recommendations && data.followup_recommendations.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <UserPlus className="h-3.5 w-3.5" />
            Recommended follow-ups
          </h3>
          <div className="max-h-56 space-y-2 overflow-y-auto">
            {data.followup_recommendations.map((rec, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2.5 text-xs"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`font-semibold uppercase ${PRIORITY_STYLES[rec.priority] || ''}`}>
                    {rec.priority}
                  </span>
                  <span className="text-slate-500">{rec.source}</span>
                  {rec.suggested_channel && (
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">
                      via {rec.suggested_channel}
                    </span>
                  )}
                </div>
                <p className="mt-1 font-medium text-slate-200">{rec.action}</p>
                <p className="text-slate-500">{rec.reason}</p>
                {rec.contact_name && (
                  <p className="mt-1 text-slate-400">
                    Patient: {rec.contact_name}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {data && !data.findings?.length && !data.followup_recommendations?.length && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-800/40 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-300">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          No compliance issues detected. Patient service data looks healthy.
        </div>
      )}
    </div>
  );
}
