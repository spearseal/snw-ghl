'use client';

import { memo, type HTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  hover?: boolean;
  accent?: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'none';
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const ACCENT_BORDER = {
  primary: 'border-l-4 border-l-primary',
  success: 'border-l-4 border-l-success',
  warning: 'border-l-4 border-l-warning',
  danger: 'border-l-4 border-l-danger',
  info: 'border-l-4 border-l-info',
  none: '',
};

const PADDING = {
  none: '',
  sm: 'p-4',
  md: 'p-5 sm:p-6',
  lg: 'p-6 sm:p-8',
};

export const Card = memo(function Card({
  children,
  className,
  hover = false,
  accent = 'none',
  padding = 'md',
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-card border border-border bg-surface-raised shadow-card',
        'transition-all duration-base',
        hover && 'hover:border-border hover:shadow-card-hover',
        ACCENT_BORDER[accent],
        PADDING[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
});

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export const CardHeader = memo(function CardHeader({
  title,
  description,
  action,
  className,
}: CardHeaderProps) {
  return (
    <div className={cn('mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div className="min-w-0">
        <h3 className="text-card-title">{title}</h3>
        {description && <p className="mt-1 text-helper">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
});
