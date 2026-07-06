'use client';

import { useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import type { TreatmentPlan } from '@/components/treatment/TreatmentPlanList';

export interface IntakeFormData {
  patient_name: string;
  email: string;
  phone: string;
  contact_id: string;
  date_of_birth: string;
  skin_concerns: string;
  allergies: string;
  current_medications: string;
  treatment_goals: string;
  budget_range: string;
  preferred_days: string;
  medical_conditions: string;
  consent_acknowledged: boolean;
}

const EMPTY: IntakeFormData = {
  patient_name: '',
  email: '',
  phone: '',
  contact_id: '',
  date_of_birth: '',
  skin_concerns: '',
  allergies: '',
  current_medications: '',
  treatment_goals: '',
  budget_range: '',
  preferred_days: '',
  medical_conditions: '',
  consent_acknowledged: false,
};

interface HealthIntakeFormProps {
  onSubmitted?: (plan: TreatmentPlan) => void;
  snowflakePasscode?: string;
}

export default function HealthIntakeForm({ onSubmitted, snowflakePasscode }: HealthIntakeFormProps) {
  const [form, setForm] = useState<IntakeFormData>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const update = (key: keyof IntakeFormData, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const params = new URLSearchParams();
      if (snowflakePasscode?.trim()) {
        params.set('snowflake_passcode', snowflakePasscode.trim());
      }
      const qs = params.toString();
      const res = await apiFetch(
        `/api/intake/submit${qs ? `?${qs}` : ''}`,
        { method: 'POST', body: JSON.stringify(form) },
        120_000,
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Intake submission failed');
      }
      setSuccess(`Intake saved — treatment plan generated for ${form.patient_name}.`);
      setForm(EMPTY);
      if (data.plan && onSubmitted) {
        onSubmitted(data.plan);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submission failed');
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100';

  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-emerald-200 bg-emerald-50/50 p-5 dark:border-emerald-800/40 dark:bg-emerald-950/20">
      <div>
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Health intake form</h2>
        <p className="text-xs text-slate-500">
          Submit patient health details to generate a personalized Snowflake-backed treatment plan.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Patient name *</label>
          <input required value={form.patient_name} onChange={(e) => update('patient_name', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Contact ID (optional)</label>
          <input value={form.contact_id} onChange={(e) => update('contact_id', e.target.value)} placeholder="GHL / Snowflake ID" className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Email</label>
          <input type="email" value={form.email} onChange={(e) => update('email', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Phone</label>
          <input value={form.phone} onChange={(e) => update('phone', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Date of birth</label>
          <input type="date" value={form.date_of_birth} onChange={(e) => update('date_of_birth', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Budget range</label>
          <select value={form.budget_range} onChange={(e) => update('budget_range', e.target.value)} className={inputClass}>
            <option value="">Select…</option>
            <option value="under-500">Under $500</option>
            <option value="500-1500">$500 – $1,500</option>
            <option value="1500-5000">$1,500 – $5,000</option>
            <option value="5000+">$5,000+</option>
          </select>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Skin concerns</label>
        <textarea rows={2} value={form.skin_concerns} onChange={(e) => update('skin_concerns', e.target.value)} placeholder="Acne, hyperpigmentation, fine lines…" className={inputClass} />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Treatment goals</label>
        <textarea rows={2} value={form.treatment_goals} onChange={(e) => update('treatment_goals', e.target.value)} placeholder="Desired outcomes and timeline…" className={inputClass} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Allergies</label>
          <textarea rows={2} value={form.allergies} onChange={(e) => update('allergies', e.target.value)} placeholder="None or list allergies" className={inputClass} />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Current medications</label>
          <textarea rows={2} value={form.current_medications} onChange={(e) => update('current_medications', e.target.value)} className={inputClass} />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Medical conditions</label>
        <textarea rows={2} value={form.medical_conditions} onChange={(e) => update('medical_conditions', e.target.value)} className={inputClass} />
      </div>
      <div>
        <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">Preferred appointment days</label>
        <input value={form.preferred_days} onChange={(e) => update('preferred_days', e.target.value)} placeholder="e.g. Tue/Thu mornings" className={inputClass} />
      </div>

      <label className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-400">
        <input
          type="checkbox"
          checked={form.consent_acknowledged}
          onChange={(e) => update('consent_acknowledged', e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded accent-indigo-600"
        />
        Patient consents to HIPAA-compliant storage of health information for treatment planning.
      </label>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800/60 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300">
          {success}
        </div>
      )}

      <button
        type="submit"
        disabled={loading || !form.consent_acknowledged}
        className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        Submit intake &amp; generate plan
      </button>
    </form>
  );
}
