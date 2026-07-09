import { cn } from '@/lib/cn';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('shimmer rounded-lg', className)} aria-hidden />
  );
}

export function PageHeaderSkeleton() {
  return (
    <div className="mb-8 space-y-3" aria-busy="true" aria-label="Loading page header">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-4 w-full max-w-lg" />
    </div>
  );
}

export function CardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-busy="true" aria-label="Loading cards">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-36 rounded-card" />
      ))}
    </div>
  );
}

export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading content">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true" aria-label="Loading table">
      <Skeleton className="h-10 w-full rounded-card" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
