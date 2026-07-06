'use client';

import { AlertTriangle, Calendar, ClipboardList } from 'lucide-react';

export interface TreatmentPhase {
  phase: number;
  title: string;
  duration_weeks: number;
  services: string[];
  priority: string;
  notes: string;
}

export interface TreatmentPlan {
  patient_id: string;
  patient_name: string;
  source: string;
  intake_status: 'complete' | 'partial' | 'none' | string;
  current_stage: string;
  current_stage_label: string;
  open_pipeline_value: number;
  open_opportunities: number;
  recommended_services: string[];
  plan_phases: TreatmentPhase[];
  risk_flags: string[];
  days_inactive?: number | null;
  next_action: string;
  health_summary?: {
    skin_concerns?: string | null;
    treatment_goals?: string | null;
    allergies?: string | null;
    budget_range?: string | null;
    preferred_days?: string | null;
  };
}

const STAGE_STYLES: Record<string, string> = {
  consultation: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
  active_treatment: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  maintenance: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
  re_engagement: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
};

const INTAKE_STYLES: Record<string, string> = {
  complete: 'text-emerald-600 dark:text-emerald-400',
  partial: 'text-amber-600 dark:text-amber-400',
  none: 'text-red-600 dark:text-red-400',
};

export default function TreatmentPlanList({ plans }: { plans: TreatmentPlan[] }) {
  if (!plans.length) {
    return (
      <p className="text-sm text-slate-500">
        No treatment plans yet. Submit a health intake form or connect Snowflake patient data.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {plans.map((plan) => (
        <article
          key={`${plan.source}-${plan.patient_id}`}
          className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900/50"
        >
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                  {plan.patient_name}
                </h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide ${
                    STAGE_STYLES[plan.current_stage] || STAGE_STYLES.consultation
                  }`}
                >
                  {plan.current_stage_label}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                {plan.source} · Intake:{' '}
                <span className={INTAKE_STYLES[plan.intake_status] || ''}>
                  {plan.intake_status}
                </span>
                {plan.open_pipeline_value > 0 && (
                  <> · ${plan.open_pipeline_value.toLocaleString()} pipeline</>
                )}
              </p>
            </div>
            {plan.risk_flags.length > 0 && (
              <div className="flex items-center gap-1 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-300">
                <AlertTriangle className="h-3.5 w-3.5" />
                Clinical review
              </div>
            )}
          </div>

          {plan.health_summary?.treatment_goals && (
            <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">
              <span className="font-medium text-slate-700 dark:text-slate-300">Goals:</span>{' '}
              {plan.health_summary.treatment_goals}
            </p>
          )}

          <div className="mb-3 flex flex-wrap gap-1.5">
            {plan.recommended_services.map((svc) => (
              <span
                key={svc}
                className="rounded-full bg-violet-100 px-2.5 py-0.5 text-xs text-violet-700 dark:bg-violet-900/40 dark:text-violet-300"
              >
                {svc}
              </span>
            ))}
          </div>

          <div className="space-y-2">
            {plan.plan_phases.map((phase) => (
              <div
                key={phase.phase}
                className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-950/40"
              >
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                    {phase.phase}
                  </span>
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
                    {phase.title}
                  </span>
                  <span className="flex items-center gap-1 text-xs text-slate-500">
                    <Calendar className="h-3 w-3" />
                    {phase.duration_weeks}w
                  </span>
                  <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] uppercase dark:bg-slate-800">
                    {phase.priority}
                  </span>
                </div>
                <p className="text-xs text-slate-500">{phase.notes}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {phase.services.map((s) => (
                    <span key={s} className="text-xs text-slate-600 dark:text-slate-400">
                      · {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <p className="mt-3 flex items-start gap-2 text-xs text-indigo-600 dark:text-indigo-300">
            <ClipboardList className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {plan.next_action}
          </p>

          {plan.risk_flags.length > 0 && (
            <ul className="mt-2 space-y-1">
              {plan.risk_flags.map((flag) => (
                <li key={flag} className="flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-3 w-3" />
                  {flag}
                </li>
              ))}
            </ul>
          )}
        </article>
      ))}
    </div>
  );
}
