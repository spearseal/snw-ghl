import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { PaginatedMeta } from '@/lib/types/common';
import { cn } from '@/lib/cn';

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
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      aria-label="Pagination"
    >
      <p className="text-sm text-slate-500">
        Showing <span className="font-medium text-slate-700 dark:text-slate-300">{start}</span>
        –<span className="font-medium text-slate-700 dark:text-slate-300">{end}</span> of{' '}
        <span className="font-medium text-slate-700 dark:text-slate-300">{meta.total}</span>
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {onPageSizeChange && (
          <label className="flex items-center gap-2 text-sm text-slate-500">
            <span className="sr-only sm:not-sr-only">Per page</span>
            <select
              value={meta.page_size}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
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

        <button
          type="button"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={!meta.has_prev}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-slate-700"
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Prev</span>
        </button>

        <span className="px-2 text-sm text-slate-600 dark:text-slate-400" aria-current="page">
          {meta.page} / {meta.total_pages}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={!meta.has_next}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-slate-700"
          aria-label="Next page"
        >
          <span className="hidden sm:inline">Next</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </nav>
  );
}
