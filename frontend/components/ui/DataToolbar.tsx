'use client';

import { Download, FileSpreadsheet, Printer, Search } from 'lucide-react';
import { cn } from '@/lib/cn';

interface DataToolbarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  onExportCsv?: () => void;
  onExportExcel?: () => void;
  onPrint?: () => void;
  extra?: React.ReactNode;
  className?: string;
}

export default function DataToolbar({
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Filter results…',
  onExportCsv,
  onExportExcel,
  onPrint,
  extra,
  className,
}: DataToolbarProps) {
  return (
    <div
      className={cn(
        'mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between print:hidden',
        className,
      )}
    >
      <div className="relative min-w-0 flex-1 sm:max-w-xs">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          aria-hidden
        />
        <input
          type="search"
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={searchPlaceholder}
          aria-label="Filter results"
          className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 dark:border-slate-700 dark:bg-slate-950"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {extra}
        {onExportCsv && (
          <button
            type="button"
            onClick={onExportCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            CSV
          </button>
        )}
        {onExportExcel && (
          <button
            type="button"
            onClick={onExportExcel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden />
            Excel
          </button>
        )}
        {onPrint && (
          <button
            type="button"
            onClick={onPrint}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <Printer className="h-3.5 w-3.5" aria-hidden />
            Print
          </button>
        )}
      </div>
    </div>
  );
}
