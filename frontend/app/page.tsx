'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw, Search } from 'lucide-react';
import { apiFetch, getToken } from '@/lib/api';

interface QueryResult {
  score: number;
  source: string;
  entity: string;
  record_id: string;
  text: string;
}

interface QueryResponse {
  answer: string;
  results: QueryResult[];
  total_chunks: number;
  searched_sources?: string[];
  indexed_sources?: string[];
  connected_sources?: Record<string, boolean>;
  load_errors?: Record<string, string>;
}

interface HealthResponse {
  status: string;
  indexed_chunks: number;
  last_indexed: string | null;
  connected_sources?: Record<string, boolean>;
  indexed_sources?: string[];
  source_chunks?: Record<string, number>;
}

interface Connection {
  id: string;
  type: 'snowflake' | 'ghl';
  status: string;
}

function formatRefreshError(data: {
  detail?: string | {
    message?: string;
    errors?: Record<string, string>;
    skipped?: Record<string, string>;
    hint?: string;
  };
}): string {
  const detail = data.detail;
  if (typeof detail === 'string') return detail;
  const parts: string[] = [detail?.message || 'Index refresh failed'];
  if (detail?.errors) {
    for (const [source, msg] of Object.entries(detail.errors)) {
      parts.push(`${source}: ${msg}`);
    }
  }
  if (detail?.skipped) {
    for (const [source, msg] of Object.entries(detail.skipped)) {
      parts.push(`${source} (skipped): ${msg}`);
    }
  }
  if (detail?.hint) parts.push(detail.hint);
  return parts.join('\n');
}

const SOURCE_LABELS: Record<string, string> = {
  snowflake: 'Snowflake',
  ghl: 'GoHighLevel',
};

export default function Home() {
  const router = useRouter();
  const [question, setQuestion] = useState('');
  const [maskPhi, setMaskPhi] = useState(true);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const snowflakeConnected = connections.some(
    (c) => c.type === 'snowflake' && c.status === 'connected'
  );
  const ghlConnected = connections.some(
    (c) => c.type === 'ghl' && c.status === 'connected'
  );

  const fetchHealth = useCallback(async () => {
    try {
      const res = await apiFetch('/api/health');
      if (res.ok) setHealth(await res.json());
    } catch {
      setHealth(null);
    }
  }, []);

  const fetchConnections = useCallback(async () => {
    try {
      const res = await apiFetch('/api/connections');
      if (res.ok) setConnections(await res.json());
    } catch {
      setConnections([]);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchHealth();
    fetchConnections();
  }, [router, fetchHealth, fetchConnections]);

  const refreshIndex = async () => {
    setRefreshing(true);
    setError(null);
    try {
      if (snowflakeConnected && !snowflakePasscode.trim()) {
        throw new Error(
          'Enter your current Snowflake MFA code (6 digits from your authenticator app).'
        );
      }
      const res = await apiFetch('/api/index/refresh', {
        method: 'POST',
        body: JSON.stringify({
          snowflake_passcode: snowflakePasscode.trim() || undefined,
          limit_per_entity: 500,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(formatRefreshError(data));
      }
      setSnowflakePasscode('');
      await fetchHealth();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Index refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const runQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    if (!snowflakeConnected && !ghlConnected) {
      setError(
        'No data sources connected. Go to DB Connectors and test your Snowflake and/or GoHighLevel connection first.'
      );
      return;
    }

    if (snowflakeConnected && !snowflakePasscode.trim()) {
      setError(
        'Enter your current Snowflake MFA code — data is loaded from connected sources when you query.'
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const res = await apiFetch('/api/query', {
        method: 'POST',
        body: JSON.stringify({
          question,
          top_k: 5,
          mask_phi: maskPhi,
          load_fresh: true,
          limit_per_entity: 500,
          snowflake_passcode: snowflakePasscode.trim() || undefined,
        }),
      }, 120_000);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string' ? data.detail : 'Query failed'
        );
      }
      setResponse(data);
      setSnowflakePasscode('');
      await fetchHealth();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  const connectedList = [
    snowflakeConnected && 'Snowflake',
    ghlConnected && 'GoHighLevel',
  ].filter(Boolean);

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Query Console</h1>
        <p className="text-sm text-slate-400">
          Ask natural-language questions. Data is loaded from each connected source
          into memory, then searched independently.
        </p>
      </div>

      {/* Connected sources + memory status */}
      <div className="mb-6 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-500">Connected:</span>
              {connectedList.length > 0 ? (
                connectedList.map((name) => (
                  <span
                    key={name}
                    className="rounded-full border border-emerald-700/50 bg-emerald-900/30 px-2.5 py-0.5 text-xs text-emerald-300"
                  >
                    {name}
                  </span>
                ))
              ) : (
                <span className="text-amber-400 text-xs">None — connect in DB Connectors</span>
              )}
            </div>
            <div className="text-sm text-slate-300">
              {health ? (
                <>
                  <span className="font-medium">{health.indexed_chunks}</span> chunks
                  in memory
                  {health.indexed_sources && health.indexed_sources.length > 0 && (
                    <span className="text-slate-500">
                      {' '}
                      ({health.indexed_sources.map((s) => SOURCE_LABELS[s] || s).join(', ')})
                    </span>
                  )}
                  {health.last_indexed && (
                    <span className="text-slate-500">
                      {' '}
                      · updated {new Date(health.last_indexed + 'Z').toLocaleString()}
                    </span>
                  )}
                </>
              ) : (
                <span className="text-amber-400">Backend unreachable</span>
              )}
            </div>
          </div>
          <button
            onClick={refreshIndex}
            disabled={refreshing || (!snowflakeConnected && !ghlConnected)}
            className="flex shrink-0 items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-200 transition hover:bg-slate-700 disabled:opacity-50"
            title="Manually reload connected sources into memory"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh Memory
          </button>
        </div>
        {snowflakeConnected && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-800 pt-3">
            <label htmlFor="snowflake-mfa" className="text-xs text-slate-400">
              Snowflake MFA code
            </label>
            <input
              id="snowflake-mfa"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={snowflakePasscode}
              onChange={(e) => setSnowflakePasscode(e.target.value.replace(/\D/g, ''))}
              placeholder="6-digit code"
              className="w-32 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-sm text-slate-100 outline-none focus:border-indigo-500"
            />
            <span className="text-xs text-slate-500">
              Required to load Snowflake data (expires every ~30s)
            </span>
          </div>
        )}
      </div>

      {/* Query input */}
      <form onSubmit={runQuery} className="mb-6">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Show contacts from Snowflake with open opportunities"
              className="w-full rounded-xl border border-slate-700 bg-slate-900 py-3 pl-11 pr-4 text-slate-100 placeholder-slate-500 outline-none transition focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Search className="h-5 w-5" />
            )}
            Query
          </button>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm text-slate-400">
          <input
            type="checkbox"
            checked={maskPhi}
            onChange={(e) => setMaskPhi(e.target.checked)}
            className="h-4 w-4 rounded border-slate-600 bg-slate-800 accent-indigo-500"
          />
          Mask PHI in results (recommended)
        </label>
      </form>

      {/* Output section */}
      <section aria-label="Output">
        {error && (
          <div className="mb-4 whitespace-pre-wrap rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {response && (
          <div className="space-y-4">
            <div className="rounded-xl border border-indigo-800/50 bg-indigo-950/30 px-4 py-3">
              <p className="text-sm font-medium text-indigo-200">
                {response.answer}
              </p>
              {response.searched_sources && response.searched_sources.length > 0 && (
                <p className="mt-1 text-xs text-indigo-300/70">
                  Searched:{' '}
                  {response.searched_sources
                    .map((s) => SOURCE_LABELS[s] || s)
                    .join(', ')}
                </p>
              )}
            </div>

            {response.results.map((r, i) => (
              <div
                key={i}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span
                    className={`rounded-full px-2.5 py-1 uppercase tracking-wide ${
                      r.source === 'snowflake'
                        ? 'bg-sky-900/40 text-sky-300'
                        : 'bg-indigo-900/40 text-indigo-300'
                    }`}
                  >
                    {SOURCE_LABELS[r.source] || r.source}
                  </span>
                  <span className="rounded-full bg-slate-800 px-2.5 py-1 text-slate-400">
                    {r.entity}
                  </span>
                  {r.record_id && (
                    <span className="rounded-full bg-slate-800 px-2.5 py-1 font-mono text-slate-500">
                      id: {r.record_id}
                    </span>
                  )}
                  <span className="ml-auto text-slate-500">
                    relevance {r.score.toFixed(2)}
                  </span>
                </div>
                <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed text-slate-300">
                  {r.text}
                </pre>
              </div>
            ))}
          </div>
        )}

        {!response && !error && (
          <div className="rounded-xl border border-dashed border-slate-800 px-4 py-12 text-center text-sm text-slate-500">
            Connect Snowflake and/or GoHighLevel, enter MFA if needed, then ask a
            question. Data loads automatically from each connected source.
          </div>
        )}
      </section>
    </main>
  );
}
