'use client';

import { forwardRef, memo, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/cn';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    'bg-primary text-white hover:bg-primary-hover shadow-sm disabled:opacity-50',
  secondary:
    'bg-surface-raised text-fg border border-border hover:bg-surface-overlay',
  ghost: 'text-fg-muted hover:bg-surface-overlay hover:text-fg',
  danger: 'bg-danger text-white hover:opacity-90',
  outline:
    'border border-border bg-transparent text-fg hover:bg-surface-overlay',
};

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 px-3 text-xs rounded-lg',
  md: 'h-9 gap-2 px-4 text-sm rounded-lg',
  lg: 'h-11 gap-2 px-6 text-sm rounded-xl',
};

const Button = memo(
  forwardRef<HTMLButtonElement, ButtonProps>(function Button(
    {
      className,
      variant = 'primary',
      size = 'md',
      loading,
      disabled,
      leftIcon,
      rightIcon,
      children,
      ...props
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        type="button"
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-fast',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
          'disabled:pointer-events-none',
          VARIANT[variant],
          SIZE[size],
          className,
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        ) : (
          leftIcon
        )}
        {children}
        {!loading && rightIcon}
      </button>
    );
  }),
);

export default Button;
