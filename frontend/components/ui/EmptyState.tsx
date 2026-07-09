import type { LucideIcon } from 'lucide-react';
import { Inbox } from 'lucide-react';
import { cn } from '@/lib/cn';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-card border border-dashed border-border px-6 py-16 text-center',
        className,
      )}
      role="status"
    >
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-overlay">
        <Icon className="h-6 w-6 text-fg-subtle" aria-hidden />
      </div>
      <h3 className="text-section-title text-base">{title}</h3>
      {description && <p className="mt-2 max-w-sm text-body">{description}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
