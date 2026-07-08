'use client';

import { useCallback, useEffect, useState } from 'react';
import { Database, Layers, Loader2, Sparkles } from 'lucide-react';
import { apiFetch } from '@/lib/api';

export interface SemanticSummary {
  built: boolean;
  model_name: string;
  model_description: string;
  configured_sources?: Array<{ name: string; type: string }>;
  entities: number;
  dimensions: number;
  facts: number;
  measures: number;
  relationships: number;
  entity_samples: Array<{
    name: string;
    business_name: string;
    entity_type: string;
    source_table: string;
  }>;
  measure_samples: Array<{
    name: string;
    business_name: string;
    expression: string;
    source_table: string;
  }>;
  suggested_questions: string[];
}

interface SemanticLayerPanelProps {
  snowflakeConnected: boolean;
  ghlConnected: boolean;
  snowflakeNeedsMfa: boolean;
  snowflakePasscode: string;
  onSuggestedQuestion: (q: string) => void;
  onError: (msg: string | null) => void;
}

export default function SemanticLayerPanel({
  snowflakeConnected,
  ghlConnected,
  snowflakeNeedsMfa,
  snowflakePasscode,
  onSuggestedQuestion,
  onError,
}: SemanticLayerPanelProps) {
  const [summary, setSummary] = useState<SemanticSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [discovering, setDiscovering] = useState(false);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await apiFetch('/api/semantic/summary');
      if (res.ok) {
        setSummary(await res.json());
      } else {
        setSummary(null);
      }
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const buildModel = async () => {
    if (!snowflakeConnected && !ghlConnected) {
      onError('Connect Snowflake or GoHighLevel in DB Connectors and test the connection first.');
      return;
    }
    if (snowflakeConnected && snowflakeNeedsMfa && !snowflakePasscode.trim()) {
      onError('Enter your Snowflake MFA code to build the semantic model.');
      return;
    }
    setBuilding(true);
    onError(null);
    try {
      const res = await apiFetch('/api/semantic/build', {
        method: 'POST',
        body: JSON.stringify({
          profile: true,
          snowflake_passcode: snowflakePasscode.trim() || undefined,
        }),
      }, 180_000);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Semantic build failed');
      }
      await fetchSummary();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Semantic build failed');
    } finally {
      setBuilding(false);
    }
  };

  const discoverMetadata = async () => {
    if (snowflakeConnected && snowflakeNeedsMfa && !snowflakePasscode.trim()) {
      onError('Enter your Snowflake MFA code to discover metadata.');
      return;
    }
    setDiscovering(true);
    onError(null);
    try {
      const res = await apiFetch('/api/semantic/discover', {
        method: 'POST',
        body: JSON.stringify({
          snowflake_passcode: snowflakePasscode.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Discovery failed');
      }
      await fetchSummary();
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Discovery failed');
    } finally {
      setDiscovering(false);
    }
  };

  if (loading) {
    return (
      <div className="mb-6 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/40">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading semantic layer…
      </div>
    );
  }

  return (
    <div className="mb-6 rounded-xl border border-indigo-200/60 bg-indigo-50/50 px-4 py-4 dark:border-indigo-900/40 dark:bg-indigo-950/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-indigo-500" />
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Semantic Layer
            </h2>
            {summary?.built ? (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                Active
              </span>
            ) : (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                Not built
              </span>
            )}
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            {summary?.built
              ? 'Spagent uses business entities, dimensions, and measures to generate smarter SQL.'
              : 'Build a semantic model to help Spagent understand your data sources.'}
          </p>
          {summary?.configured_sources && summary.configured_sources.length > 0 ? (
            <p className="text-xs text-slate-500">
              Sources: {summary.configured_sources.map((s) => s.type).join(', ')}
            </p>
          ) : (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              No sources linked — connect Snowflake or GHL in DB Connectors first.
            </p>
          )}
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={discoverMetadata}
            disabled={discovering || building || (!snowflakeConnected && !ghlConnected)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {discovering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Database className="h-3.5 w-3.5" />}
            Discover
          </button>
          <button
            type="button"
            onClick={buildModel}
            disabled={building || discovering}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {building ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Build Model
          </button>
        </div>
      </div>

      {summary?.built && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          {[
            { label: 'Entities', value: summary.entities },
            { label: 'Dimensions', value: summary.dimensions },
            { label: 'Facts', value: summary.facts },
            { label: 'Measures', value: summary.measures },
            { label: 'Relationships', value: summary.relationships },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-slate-200/80 bg-white/80 px-3 py-2 dark:border-slate-800 dark:bg-slate-900/60"
            >
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-50">{stat.value}</p>
              <p className="text-xs text-slate-500">{stat.label}</p>
            </div>
          ))}
        </div>
      )}

      {summary?.entity_samples && summary.entity_samples.length > 0 && (
        <div className="mt-3 border-t border-indigo-200/40 pt-3 dark:border-indigo-900/40">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Business entities
          </p>
          <div className="flex flex-wrap gap-1.5">
            {summary.entity_samples.map((e) => (
              <span
                key={e.name}
                title={`${e.source_table} (${e.entity_type})`}
                className="rounded-full border border-indigo-200 bg-white px-2.5 py-1 text-xs text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-200"
              >
                {e.business_name}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary?.suggested_questions && summary.suggested_questions.length > 0 && (
        <div className="mt-3 border-t border-indigo-200/40 pt-3 dark:border-indigo-900/40">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Suggested questions
          </p>
          <div className="flex flex-wrap gap-2">
            {summary.suggested_questions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onSuggestedQuestion(q)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/40"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
