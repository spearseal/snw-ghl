'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import {
  Cable,
  CheckCircle2,
  Database,
  Loader2,
  Plug,
  Plus,
  Snowflake,
  Trash2,
  XCircle,
} from 'lucide-react';
import { apiFetch, getToken } from '@/lib/api';

interface Connection {
  id: string;
  name: string;
  type: 'snowflake' | 'ghl';
  is_default: boolean;
  config: Record<string, string>;
  status: 'untested' | 'connected' | 'error';
  last_tested: string | null;
}

const SNOWFLAKE_FIELDS = [
  { key: 'account', label: 'Account', required: true },
  { key: 'user', label: 'User', required: true },
  { key: 'password', label: 'Password', required: true, secret: true },
  { key: 'warehouse', label: 'Warehouse', required: false },
  { key: 'database', label: 'Database', required: false },
  { key: 'schema', label: 'Schema', required: false },
  { key: 'role', label: 'Role', required: false },
  { key: 'passcode', label: 'Passcode (MFA)', required: true, secret: true },
];

const GHL_FIELDS = [
  { key: 'api_key', label: 'API Key', required: true, secret: true },
  { key: 'base_url', label: 'Base URL', required: false },
  { key: 'location_id', label: 'Location ID', required: false },
];

export default function ConnectorsPage() {
  const router = useRouter();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState<'snowflake' | 'ghl'>('snowflake');
  const [newConfig, setNewConfig] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const loadConnections = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/connections');
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load connections');
      setConnections(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load connections');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push('/login');
      return;
    }
    loadConnections();
  }, [router, loadConnections]);

  const testConnection = async (id: string) => {
    setTesting(id);
    try {
      const res = await apiFetch(`/api/connections/${id}/test`, {
        method: 'POST',
      });
      const data = await res.json();
      setTestResults((prev) => ({ ...prev, [id]: data.detail }));
      setConnections((prev) =>
        prev.map((c) =>
          c.id === id
            ? { ...c, status: data.status, last_tested: data.last_tested }
            : c
        )
      );
    } catch {
      setTestResults((prev) => ({ ...prev, [id]: 'Test request failed' }));
    } finally {
      setTesting(null);
    }
  };

  const deleteConnection = async (id: string) => {
    if (!confirm('Delete this connection?')) return;
    const res = await apiFetch(`/api/connections/${id}`, { method: 'DELETE' });
    if (res.ok) {
      setConnections((prev) => prev.filter((c) => c.id !== id));
    }
  };

  const createConnection = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch('/api/connections', {
        method: 'POST',
        body: JSON.stringify({
          name: newName,
          type: newType,
          config: newConfig,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Failed to create connection'
        );
      }
      setConnections((prev) => [...prev, data]);
      setShowForm(false);
      setNewName('');
      setNewConfig({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create connection');
    } finally {
      setSaving(false);
    }
  };

  const fields = newType === 'snowflake' ? SNOWFLAKE_FIELDS : GHL_FIELDS;

  const statusBadge = (c: Connection) => {
    if (c.status === 'connected')
      return (
        <span className="flex items-center gap-1 rounded-full border border-emerald-700/50 bg-emerald-900/30 px-2 py-0.5 text-xs text-emerald-300">
          <CheckCircle2 className="h-3.5 w-3.5" /> Connected
        </span>
      );
    if (c.status === 'error')
      return (
        <span className="flex items-center gap-1 rounded-full border border-red-800/60 bg-red-950/40 px-2 py-0.5 text-xs text-red-300">
          <XCircle className="h-3.5 w-3.5" /> Error
        </span>
      );
    return (
      <span className="rounded-full border border-slate-700 bg-slate-800/50 px-2 py-0.5 text-xs text-slate-400">
        Not tested
      </span>
    );
  };

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-600/20 p-3">
            <Cable className="h-6 w-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">DB Connectors</h1>
            <p className="text-sm text-slate-400">
              Connect to Snowflake and GoHighLevel, or add new connections
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
        >
          <Plus className="h-4 w-4" />
          New Connection
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* New connection form */}
      {showForm && (
        <form
          onSubmit={createConnection}
          className="mb-6 rounded-2xl border border-indigo-800/50 bg-slate-900/60 p-6"
        >
          <h2 className="mb-4 font-medium">Create New Connection</h2>
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm text-slate-400">
                Connection Name
              </label>
              <input
                required
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Prod Snowflake"
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 placeholder-slate-600 outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm text-slate-400">
                Type
              </label>
              <select
                value={newType}
                onChange={(e) => {
                  setNewType(e.target.value as 'snowflake' | 'ghl');
                  setNewConfig({});
                }}
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500"
              >
                <option value="snowflake">Snowflake</option>
                <option value="ghl">GoHighLevel</option>
              </select>
            </div>
            {fields.map((f) => (
              <div key={f.key}>
                <label className="mb-1.5 block text-sm text-slate-400">
                  {f.label}
                  {f.required && <span className="text-red-400"> *</span>}
                </label>
                <input
                  type={'secret' in f && f.secret ? 'password' : 'text'}
                  required={f.required}
                  value={newConfig[f.key] || ''}
                  onChange={(e) =>
                    setNewConfig((prev) => ({
                      ...prev,
                      [f.key]: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-indigo-500"
                />
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Save Connection
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-lg px-4 py-2 text-sm text-slate-400 transition hover:bg-slate-800"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Connection cards */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
        </div>
      ) : connections.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 px-4 py-12 text-center text-sm text-slate-500">
          No connections yet. Add credentials to .env or create a new
          connection.
        </div>
      ) : (
        <div className="space-y-4">
          {connections.map((c) => (
            <div
              key={c.id}
              className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-slate-800 p-2.5">
                    {c.type === 'snowflake' ? (
                      <Snowflake className="h-5 w-5 text-sky-400" />
                    ) : (
                      <Database className="h-5 w-5 text-indigo-400" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      {statusBadge(c)}
                    </div>
                    <p className="text-xs text-slate-500">
                      {c.type === 'snowflake' ? 'Snowflake' : 'GoHighLevel'}
                      {c.last_tested &&
                        ` · last tested ${new Date(c.last_tested).toLocaleString()}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => testConnection(c.id)}
                    disabled={testing === c.id}
                    className="flex items-center gap-2 rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-slate-200 transition hover:bg-slate-700 disabled:opacity-50"
                  >
                    {testing === c.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Plug className="h-4 w-4" />
                    )}
                    Connect
                  </button>
                  {!c.is_default && (
                    <button
                      onClick={() => deleteConnection(c.id)}
                      title="Delete connection"
                      className="rounded-lg p-2 text-slate-500 transition hover:bg-red-950/40 hover:text-red-400"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              {testResults[c.id] && (
                <p
                  className={`mt-3 rounded-lg px-3 py-2 text-xs ${
                    c.status === 'connected'
                      ? 'bg-emerald-950/40 text-emerald-300'
                      : 'bg-red-950/40 text-red-300'
                  }`}
                >
                  {testResults[c.id]}
                </p>
              )}

              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(c.config)
                  .filter(([, v]) => v)
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className="rounded-full bg-slate-800 px-2.5 py-1 font-mono text-[11px] text-slate-400"
                    >
                      {k}: {v}
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
