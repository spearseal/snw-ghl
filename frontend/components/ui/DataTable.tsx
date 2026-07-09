'use client';

import { memo, type ReactNode } from 'react';
import { cn } from '@/lib/cn';

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  className?: string;
  render: (row: T) => ReactNode;
  mobileLabel?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  emptyState?: ReactNode;
  className?: string;
  stickyHeader?: boolean;
}

function DataTableInner<T>({
  columns,
  data,
  keyExtractor,
  emptyState,
  className,
  stickyHeader = true,
}: DataTableProps<T>) {
  if (data.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <>
      {/* Desktop table */}
      <div
        className={cn(
          'hidden overflow-hidden rounded-card border border-border bg-surface-raised shadow-card md:block',
          className,
        )}
      >
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead
              className={cn(
                'border-b border-border bg-surface text-xs font-medium uppercase tracking-wide text-fg-subtle',
                stickyHeader && 'sticky top-0 z-10',
              )}
            >
              <tr>
                {columns.map((col) => (
                  <th key={col.key} scope="col" className={cn('px-4 py-3', col.className)}>
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {data.map((row) => (
                <tr
                  key={keyExtractor(row)}
                  className="transition-colors duration-fast hover:bg-surface"
                >
                  {columns.map((col) => (
                    <td key={col.key} className={cn('px-4 py-3 text-fg-muted', col.className)}>
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile cards */}
      <div className="space-y-3 md:hidden">
        {data.map((row) => (
          <div
            key={keyExtractor(row)}
            className="rounded-card border border-border bg-surface-raised p-4 shadow-card"
          >
            <dl className="space-y-2">
              {columns.map((col) => (
                <div key={col.key} className="flex justify-between gap-4 text-sm">
                  <dt className="text-fg-subtle">{col.mobileLabel ?? col.header}</dt>
                  <dd className="text-right font-medium text-fg">{col.render(row)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </>
  );
}

const DataTable = memo(DataTableInner) as typeof DataTableInner;
export default DataTable;
