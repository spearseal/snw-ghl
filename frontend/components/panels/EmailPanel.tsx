'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Mail, Send, Settings2 } from 'lucide-react';
import { apiFetch } from '@/lib/api';

interface EmailSettings {
  provider: 'ghl' | 'smtp';
  inactive_days: number;
  subject_template: string;
  body_template: string;
  from_email: string;
  from_name: string;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  enabled: boolean;
}

interface FollowupCandidate {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  source: string;
  days_inactive?: number;
}

const DEFAULT_SETTINGS: EmailSettings = {
  provider: 'ghl',
  inactive_days: 90,
  subject_template: "We'd love to reconnect — {{name}}",
  body_template: `<p>Hi {{name}},</p>
<p>We noticed it has been a while since we last connected. We'd love to help you with your next step.</p>
<p>Reply to this email anytime — we're here for you.</p>`,
  from_email: '',
  from_name: 'Your Team',
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_use_tls: true,
  enabled: true,
};

export default function EmailPanel() {
  const [settings, setSettings] = useState<EmailSettings>(DEFAULT_SETTINGS);
  const [candidates, setCandidates] = useState<FollowupCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsRes, insightsRes] = await Promise.all([
        apiFetch('/api/email/settings'),
        apiFetch('/api/insights'),
      ]);
      const settingsData = await settingsRes.json();
      const insightsData = await insightsRes.json();
      if (settingsRes.ok) {
        setSettings({ ...DEFAULT_SETTINGS, ...settingsData });
      }
      if (insightsRes.ok) {
        setCandidates(insightsData.followup_candidates || []);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load email settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch('/api/email/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save settings');
      setSettings({ ...settings, ...data });
      setMessage('Email settings saved.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const sendFollowup = async (dryRun: boolean) => {
    setSending(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch('/api/email/followup/send', {
        method: 'POST',
        body: JSON.stringify({ send_all: true, dry_run: dryRun }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Send failed');
      setMessage(
        dryRun
          ? `Dry run: would send ${data.sent} email(s) via ${data.provider}.`
          : `Sent ${data.sent} follow-up email(s) via ${data.provider}.`
      );
      if (data.errors?.length) {
        setError(data.errors.map((e: { error: string }) => e.error).join('; '));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed');
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-amber-800/40 bg-amber-950/20 px-4 py-3 text-sm text-amber-200">
        <p className="font-medium">90-day no show / no follow-up campaign</p>
        <p className="mt-1 text-xs text-amber-300/80">
          Targets customers with no activity and no follow-up for {settings.inactive_days}+ days.
          Uses GoHighLevel messaging when provider is GHL, or SMTP when configured.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-red-800/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {message && (
        <div className="rounded-xl border border-emerald-800/60 bg-emerald-950/40 px-4 py-3 text-sm text-emerald-300">
          {message}
        </div>
      )}

      <form onSubmit={saveSettings} className="space-y-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-800 dark:text-slate-200">
          <Settings2 className="h-4 w-4" />
          Campaign settings
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Provider</label>
            <select
              value={settings.provider}
              onChange={(e) =>
                setSettings((s) => ({ ...s, provider: e.target.value as 'ghl' | 'smtp' }))
              }
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            >
              <option value="ghl">GoHighLevel (recommended)</option>
              <option value="smtp">SMTP</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Inactive days threshold</label>
            <input
              type="number"
              min={30}
              max={365}
              value={settings.inactive_days}
              onChange={(e) =>
                setSettings((s) => ({ ...s, inactive_days: Number(e.target.value) }))
              }
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">From email</label>
            <input
              value={settings.from_email}
              onChange={(e) => setSettings((s) => ({ ...s, from_email: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">From name</label>
            <input
              value={settings.from_name}
              onChange={(e) => setSettings((s) => ({ ...s, from_name: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
        </div>

        {settings.provider === 'smtp' && (
          <div className="grid gap-4 sm:grid-cols-2">
            <input
              placeholder="SMTP host"
              value={settings.smtp_host}
              onChange={(e) => setSettings((s) => ({ ...s, smtp_host: e.target.value }))}
              className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              type="number"
              placeholder="SMTP port"
              value={settings.smtp_port}
              onChange={(e) => setSettings((s) => ({ ...s, smtp_port: Number(e.target.value) }))}
              className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              placeholder="SMTP user"
              value={settings.smtp_user}
              onChange={(e) => setSettings((s) => ({ ...s, smtp_user: e.target.value }))}
              className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              type="password"
              placeholder="SMTP password"
              value={settings.smtp_password}
              onChange={(e) => setSettings((s) => ({ ...s, smtp_password: e.target.value }))}
              className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
            />
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Subject (use {'{{name}}'})</label>
          <input
            value={settings.subject_template}
            onChange={(e) => setSettings((s) => ({ ...s, subject_template: e.target.value }))}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">HTML body template</label>
          <textarea
            rows={5}
            value={settings.body_template}
            onChange={(e) => setSettings((s) => ({ ...s, body_template: e.target.value }))}
            className="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3 py-2 font-mono text-xs"
          />
        </div>

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save settings'}
        </button>
      </form>

      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-800 dark:text-slate-200">
            <Mail className="h-4 w-4" />
            Follow-up candidates ({candidates.length})
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={sending || candidates.length === 0}
              onClick={() => sendFollowup(true)}
              className="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
            >
              Dry run
            </button>
            <button
              type="button"
              disabled={sending || candidates.length === 0}
              onClick={() => sendFollowup(false)}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-1.5 text-xs text-white hover:bg-emerald-600 disabled:opacity-50"
            >
              {sending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              Send all
            </button>
          </div>
        </div>
        {candidates.length === 0 ? (
          <p className="text-xs text-slate-500">
            No 90-day inactive contacts found. Connect data sources and refresh insights.
          </p>
        ) : (
          <div className="max-h-48 space-y-2 overflow-y-auto">
            {candidates.slice(0, 20).map((c) => (
              <div
                key={`${c.source}-${c.id}`}
                className="flex items-center justify-between rounded-lg bg-white dark:bg-slate-950 px-3 py-2 text-xs"
              >
                <span className="text-slate-700 dark:text-slate-300">{c.name}</span>
                <span className="text-slate-500">
                  {c.source} · {c.days_inactive ?? '?'}d inactive
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
