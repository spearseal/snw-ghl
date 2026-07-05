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

interface AgentResponse {
  answer: string;
  sql: string | null;
  reasoning: string;
  method?: string;
  row_count: number;
  rows: Record<string, unknown>[];
  schema_summary?: {
    database: string;
    schema: string;
    table_count: number;
    tables: string[];
  };
}

interface SchemaResponse {
  database: string;
  schema: string;
  table_count: number;
  tables: Array<{
    name: string;
    row_count?: number;
    columns: Array<{ name: string; type: string }>;
  }>;
}

interface HealthResponse {
  status: string;
  indexed_chunks: number;
  last_indexed: string | null;
  connected_sources?: Record<string, boolean>;
  indexed_sources?: string[];
  source_chunks?: Record<string, number>;
  snowflake_requires_passcode?: boolean;
}

interface Connection {
  id: string;
  type: 'snowflake' | 'ghl';
  status: string;
  snowflake_requires_passcode?: boolean;
  snowflake_auth_method?: 'key_pair' | 'password';
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
  const [agentResponse, setAgentResponse] = useState<AgentResponse | null>(null);
  const [schemaInfo, setSchemaInfo] = useState<SchemaResponse | null>(null);
  const [queryMode, setQueryMode] = useState<'agent' | 'memory'>('agent');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [snowflakePasscode, setSnowflakePasscode] = useState('');

  const snowflakeConnected = connections.some(
    (c) => c.type === 'snowflake' && c.status === 'connected'
  );
  const snowflakeNeedsMfa =
    health?.snowflake_requires_passcode ??
    connections.some(
      (c) =>
        c.type === 'snowflake' &&
        c.status === 'connected' &&
        c.snowflake_requires_passcode !== false
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
      if (snowflakeConnected && snowflakeNeedsMfa && !snowflakePasscode.trim()) {
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

    if (queryMode === 'agent') {
      if (!snowflakeConnected) {
        setError('Snowflake Agent requires a connected Snowflake datasource.');
        return;
      }
      if (snowflakeNeedsMfa && !snowflakePasscode.trim()) {
        setError('Enter your current Snowflake MFA code for password-based auth.');
        return;
      }
      setLoading(true);
      setError(null);
      setResponse(null);
      setAgentResponse(null);
      try {
        const res = await apiFetch('/api/agent/query', {
          method: 'POST',
          body: JSON.stringify({
            question,
            limit: 100,
            mask_phi: maskPhi,
            snowflake_passcode: snowflakePasscode.trim() || undefined,
          }),
        }, 120_000);
        const data = await res.json();
        if (!res.ok) {
          throw new Error(
            typeof data.detail === 'string' ? data.detail : 'Agent query failed'
          );
        }
        setAgentResponse(data);
        setSnowflakePasscode('');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Agent query failed');
      } finally {
        setLoading(false);
      }
      return;
    }

    if (!snowflakeConnected && !ghlConnected) {
      setError(
        'No data sources connected. Go to DB Connectors and test your Snowflake and/or GoHighLevel connection first.'
      );
      return;
    }

    if (snowflakeConnected && snowflakeNeedsMfa && !snowflakePasscode.trim()) {
      setError(
        'Enter your current Snowflake MFA code — required for password-based auth.'
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);
    setAgentResponse(null);
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

  const loadSchema = async () => {
    if (!snowflakeConnected) {
      setError('Connect Snowflake first to analyze schema.');
      return;
    }
    if (snowflakeNeedsMfa && !snowflakePasscode.trim()) {
      setError('Enter MFA code to analyze schema.');
      return;
    }
    setError(null);
    try {
      const params = snowflakePasscode.trim()
        ? `?snowflake_passcode=${encodeURIComponent(snowflakePasscode.trim())}`
        : '';
      const res = await apiFetch(`/api/snowflake/schema${params}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string' ? data.detail : 'Schema discovery failed'
        );
      }
      setSchemaInfo(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Schema discovery failed');
    }
  };

  const connectedList: string[] = [];
  if (snowflakeConnected) connectedList.push('Snowflake');
  if (ghlConnected) connectedList.push('GoHighLevel');

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Query Console</h1>
        <p className="text-sm text-slate-400">
          Snowflake Agent discovers all tables in your database/schema and answers
          with live SQL. Memory search uses pre-loaded chunks (GHL + Snowflake).
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setQueryMode('agent')}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              queryMode === 'agent'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-300'
            }`}
          >
            Snowflake Agent
          </button>
          <button
            type="button"
            onClick={() => setQueryMode('memory')}
            className={`rounded-lg px-3 py-1.5 text-sm ${
              queryMode === 'memory'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-300'
            }`}
          >
            Memory Search
          </button>
          {snowflakeConnected && queryMode === 'agent' && (
            <button
              type="button"
              onClick={loadSchema}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700"
            >
              Analyze Schema
            </button>
          )}
        </div>
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
        {snowflakeConnected && snowflakeNeedsMfa && (
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
        {snowflakeConnected && !snowflakeNeedsMfa && (
          <p className="mt-3 border-t border-slate-800 pt-3 text-xs text-emerald-400">
            Snowflake key-pair auth — no MFA code needed
          </p>
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
              placeholder={
                queryMode === 'agent'
                  ? 'e.g. give me total customers from ghl_contacts'
                  : 'e.g. Which contacts have open opportunities?'
              }
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

        {schemaInfo && queryMode === 'agent' && (
          <div className="mb-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-sm">
            <p className="mb-2 font-medium text-slate-200">
              Schema {schemaInfo.database}.{schemaInfo.schema} — {schemaInfo.table_count}{' '}
              table(s)
            </p>
            <div className="flex flex-wrap gap-2">
              {schemaInfo.tables.map((t) => (
                <span
                  key={t.name}
                  className="rounded-full bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-400"
                >
                  {t.name}
                  {t.row_count != null ? ` (${t.row_count})` : ''}
                </span>
              ))}
            </div>
          </div>
        )}

        {agentResponse && (
          <div className="space-y-4">
            <div className="rounded-xl border border-sky-800/50 bg-sky-950/30 px-4 py-3">
              <p className="text-sm font-medium text-sky-200">{agentResponse.answer}</p>
              <p className="mt-1 text-xs text-sky-300/70">{agentResponse.reasoning}</p>
              {agentResponse.schema_summary && (
                <p className="mt-1 text-xs text-sky-300/70">
                  Analyzed {agentResponse.schema_summary.table_count} tables in{' '}
                  {agentResponse.schema_summary.database}.
                  {agentResponse.schema_summary.schema}
                </p>
              )}
            </div>
            {agentResponse.sql && (
              <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-emerald-300">
                {agentResponse.sql}
              </pre>
            )}
            {agentResponse.rows.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="min-w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-900 text-xs uppercase text-slate-500">
                    <tr>
                      {Object.keys(agentResponse.rows[0]).map((col) => (
                        <th key={col} className="px-4 py-2">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {agentResponse.rows.map((row, i) => (
                      <tr key={i} className="border-t border-slate-800">
                        {Object.keys(agentResponse.rows[0]).map((col) => (
                          <td key={col} className="px-4 py-2 font-mono text-xs">
                            {String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
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
              {response.load_errors && Object.keys(response.load_errors).length > 0 && (
                <p className="mt-2 whitespace-pre-wrap text-xs text-amber-300/90">
                  {Object.entries(response.load_errors)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join('\n')}
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

        {!response && !agentResponse && !error && (
          <div className="rounded-xl border border-dashed border-slate-800 px-4 py-12 text-center text-sm text-slate-500">
            {queryMode === 'agent'
              ? 'Use Snowflake Agent to analyze all tables in your database/schema and query with natural language.'
              : 'Connect sources, refresh memory, then search indexed chunks.'}
          </div>
        )}
      </section>
    </main>
  );
}
