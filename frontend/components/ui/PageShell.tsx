'use client';

import type { ReactNode } from 'react';
import { Loader2, RefreshCw, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/cn';
import Button from './Button';
import Input from './Input';

interface PageShellProps {
  eyebrow?: string;
  eyebrowIcon?: LucideIcon;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  printTitle?: string;
  /** narrow = 64rem, default = 90rem */
  width?: 'default' | 'narrow' | 'full';
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
  width = 'default',
}: PageShellProps) {
  const widthClass =
    width === 'narrow'
      ? 'max-w-narrow'
      : width === 'full'
        ? 'max-w-none'
        : 'max-w-content';

  return (
    <div className={cn('mx-auto w-full', widthClass, className)}>
      <header className="mb-6 flex flex-col gap-4 sm:mb-8 lg:flex-row lg:items-start lg:justify-between print:mb-4">
        <div className="min-w-0">
          {eyebrow && (
            <div className="mb-2 flex items-center gap-2 text-primary">
              {EyebrowIcon && <EyebrowIcon className="h-4 w-4 shrink-0" aria-hidden />}
              <span className="text-caption font-medium uppercase tracking-wider">{eyebrow}</span>
            </div>
          )}
          <h1
            className="text-page-title"
            data-print-title={printTitle ?? title}
          >
            {title}
          </h1>
          {description && <p className="mt-2 text-body">{description}</p>}
        </div>
        {actions && (
          <div className="flex shrink-0 flex-wrap items-center gap-2 print:hidden" data-print-hide>
            {actions}
          </div>
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
    <Button onClick={onClick} loading={loading} leftIcon={!loading ? <RefreshCw className="h-4 w-4" aria-hidden /> : undefined}>
      {label}
    </Button>
  );
}

interface MfaInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function MfaInput({ value, onChange }: MfaInputProps) {
  return (
    <Input
      type="text"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, ''))}
      placeholder="Snowflake MFA"
      aria-label="Snowflake MFA code"
      inputClassName="w-28 font-mono text-xs"
    />
  );
}

interface AlertBannerProps {
  variant: 'error' | 'success' | 'warning' | 'info';
  children: ReactNode;
  className?: string;
}

const ALERT_STYLES = {
  error: 'border-danger/30 bg-danger-subtle text-danger',
  success: 'border-success/30 bg-success-subtle text-success',
  warning: 'border-warning/30 bg-warning-subtle text-warning',
  info: 'border-info/30 bg-info-subtle text-info',
};

export function AlertBanner({ variant, children, className }: AlertBannerProps) {
  return (
    <div
      role="alert"
      className={cn('mb-4 rounded-card border px-4 py-3 text-sm', ALERT_STYLES[variant], className)}
    >
      {children}
    </div>
  );
}
