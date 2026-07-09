import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { PaginatedMeta } from '@/lib/types/common';
import { cn } from '@/lib/cn';
import Button from './Button';

interface PaginationProps {
  meta: PaginatedMeta;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

export default function Pagination({
  meta,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  className,
}: PaginationProps) {
  const start = meta.total === 0 ? 0 : (meta.page - 1) * meta.page_size + 1;
  const end = Math.min(meta.page * meta.page_size, meta.total);

  return (
    <nav
      className={cn(
        'flex flex-col gap-4 rounded-card border border-border bg-surface-raised px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      aria-label="Pagination"
    >
      <p className="text-caption">
        Showing <span className="font-medium text-fg">{start}</span>
        –<span className="font-medium text-fg">{end}</span> of{' '}
        <span className="font-medium text-fg">{meta.total}</span>
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {onPageSizeChange && (
          <label className="flex items-center gap-2 text-caption">
            <span className="sr-only sm:not-sr-only">Per page</span>
            <select
              value={meta.page_size}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="h-8 rounded-lg border border-border bg-surface-raised px-2 text-sm text-fg"
              aria-label="Items per page"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>
                  {n} / page
                </option>
              ))}
            </select>
          </label>
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={!meta.has_prev}
          leftIcon={<ChevronLeft className="h-4 w-4" aria-hidden />}
        >
          Prev
        </Button>
        <span className="min-w-[4rem] text-center text-sm font-medium text-fg">
          {meta.page} / {meta.total_pages || 1}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={!meta.has_next}
          rightIcon={<ChevronRight className="h-4 w-4" aria-hidden />}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
