'use client';

import type { ReactNode } from 'react';
import { Loader2, RefreshCw, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';

interface PageShellProps {
  eyebrow?: string;
  eyebrowIcon?: LucideIcon;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  printTitle?: string;
}

export default function PageShell({
  eyebrow,
  eyebrowIcon: EyebrowIcon,
  title,
  description,
  actions,
  children,
  className,
  printTitle,
}: PageShellProps) {
  return (
    <div className={cn('mx-auto w-full max-w-5xl print:max-w-none', className)}>
      <header className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between print:mb-4">
        <div className="min-w-0">
          {eyebrow && (
            <div className="mb-1 flex items-center gap-2 text-indigo-500 dark:text-indigo-400">
              {EyebrowIcon && <EyebrowIcon className="h-5 w-5 shrink-0" aria-hidden />}
              <span className="text-xs font-medium uppercase tracking-wider">{eyebrow}</span>
            </div>
          )}
          <h1
            className="text-xl font-bold text-slate-900 dark:text-slate-50 sm:text-2xl"
            data-print-title={printTitle ?? title}
          >
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{description}</p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 flex-wrap items-center gap-2 print:hidden">{actions}</div>
        )}
      </header>
      {children}
    </div>
  );
}

interface RefreshButtonProps {
  onClick: () => void;
  loading?: boolean;
  label?: string;
}

export function RefreshButton({ onClick, loading, label = 'Refresh' }: RefreshButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 disabled:opacity-50"
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <RefreshCw className="h-4 w-4" aria-hidden />
      )}
      {label}
    </button>
  );
}

interface MfaInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function MfaInput({ value, onChange }: MfaInputProps) {
  return (
    <input
      type="text"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, ''))}
      placeholder="Snowflake MFA"
      aria-label="Snowflake MFA code"
      className="w-28 rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 dark:border-slate-700 dark:bg-slate-950"
    />
  );
}

interface AlertBannerProps {
  variant: 'error' | 'success' | 'warning';
  children: ReactNode;
  className?: string;
}

const ALERT_STYLES = {
  error: 'border-red-200 bg-red-50 text-red-800 dark:border-red-800/60 dark:bg-red-950/40 dark:text-red-300',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300',
  warning: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-200',
};

export function AlertBanner({ variant, children, className }: AlertBannerProps) {
  return (
    <div
      role="alert"
      className={cn('mb-4 rounded-xl border px-4 py-3 text-sm', ALERT_STYLES[variant], className)}
    >
      {children}
    </div>
  );
}
