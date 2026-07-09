'use client';

import { memo, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
  ariaLabel?: string;
}

export default memo(function Tabs({
  tabs,
  active,
  onChange,
  className,
  ariaLabel = 'Tabs',
}: TabsProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex flex-wrap gap-1 rounded-xl border border-border bg-surface-raised p-1',
        className,
      )}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-fast',
              isActive
                ? 'bg-primary text-white shadow-sm'
                : 'text-fg-muted hover:bg-surface-overlay hover:text-fg',
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
});
