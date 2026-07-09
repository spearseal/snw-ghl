import { memo, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

type BadgeVariant = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info';

const VARIANT: Record<BadgeVariant, string> = {
  neutral: 'bg-surface-overlay text-fg-muted border-border',
  primary: 'bg-primary-subtle text-primary border-primary/20',
  success: 'bg-success-subtle text-success border-success/20',
  warning: 'bg-warning-subtle text-warning border-warning/20',
  danger: 'bg-danger-subtle text-danger border-danger/20',
  info: 'bg-info-subtle text-info border-info/20',
};

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export default memo(function Badge({
  children,
  variant = 'neutral',
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide',
        VARIANT[variant],
        className,
      )}
    >
      {children}
    </span>
  );
});
