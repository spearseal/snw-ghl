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
}

interface HealthResponse {
  status: string;
  indexed_chunks: number;
  last_indexed: string | null;
}

export default function Home() {
  const router = useRouter();
  const [question, setQuestion] = useState('');
  const [maskPhi, setMaskPhi] = useState(true);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch('/api/health');
      if (res.ok) setHealth(await res.json());
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    fetchHealth();
  }, [router, fetchHealth]);

  const refreshIndex = async () => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await apiFetch('/api/index/refresh', {
        method: 'POST',
        body: JSON.stringify({
          include_ghl: true,
          include_snowflake: true,
          limit_per_entity: 500,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : data.detail?.message || 'Index refresh failed'
        );
      }
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
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const res = await apiFetch('/api/query', {
        method: 'POST',
        body: JSON.stringify({ question, top_k: 5, mask_phi: maskPhi }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string' ? data.detail : 'Query failed'
        );
      }
      setResponse(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Query Console</h1>
        <p className="text-sm text-slate-400">
          Ask questions across GoHighLevel and Snowflake data
        </p>
      </div>

      {/* Index status bar */}
      <div className="mb-6 flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3">
        <div className="text-sm text-slate-300">
          {health ? (
            <>
              <span className="font-medium">{health.indexed_chunks}</span>{' '}
              chunks indexed
              {health.last_indexed && (
                <span className="text-slate-500">
                  {' '}
                  · updated {new Date(health.last_indexed + 'Z').toLocaleString()}
                </span>
              )}
            </>
          ) : (
            <span className="text-amber-400">
              Backend unreachable — start the API on port 8000
            </span>
          )}
        </div>
        <button
          onClick={refreshIndex}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-200 transition hover:bg-slate-700 disabled:opacity-50"
        >
          {refreshing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Refresh Index
        </button>
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
              placeholder="e.g. Which contacts have open opportunities?"
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
          <div className="mb-4 rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {response && (
          <div className="space-y-4">
            <div className="rounded-xl border border-indigo-800/50 bg-indigo-950/30 px-4 py-3">
              <p className="text-sm font-medium text-indigo-200">
                {response.answer}
              </p>
            </div>

            {response.results.map((r, i) => (
              <div
                key={i}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-slate-800 px-2.5 py-1 uppercase tracking-wide text-slate-300">
                    {r.source}
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
            Results will appear here. Refresh the index, then ask a question.
          </div>
        )}
      </section>
    </main>
  );
}
