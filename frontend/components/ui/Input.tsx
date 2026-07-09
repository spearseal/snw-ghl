'use client';

import { forwardRef, memo, type InputHTMLAttributes, useId } from 'react';
import { cn } from '@/lib/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  error?: string;
  inputClassName?: string;
}

const Input = memo(
  forwardRef<HTMLInputElement, InputProps>(function Input(
    { label, helperText, error, className, inputClassName, id, required, ...props },
    ref,
  ) {
    const autoId = useId();
    const inputId = id ?? autoId;
    const helperId = helperText ? `${inputId}-helper` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;

    return (
      <div className={cn('flex flex-col gap-1.5', className)}>
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-fg">
            {label}
            {required && <span className="ml-0.5 text-danger" aria-hidden>*</span>}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={[helperId, errorId].filter(Boolean).join(' ') || undefined}
          className={cn(
            'h-10 w-full rounded-lg border bg-surface-raised px-3 text-sm text-fg',
            'placeholder:text-fg-subtle',
            'transition-colors duration-fast',
            'focus:border-primary focus:ring-2 focus:ring-primary/20 focus:outline-none',
            error ? 'border-danger' : 'border-border',
            inputClassName,
          )}
          {...props}
        />
        {helperText && !error && (
          <p id={helperId} className="text-helper">
            {helperText}
          </p>
        )}
        {error && (
          <p id={errorId} className="text-xs text-danger" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }),
);

export default Input;
