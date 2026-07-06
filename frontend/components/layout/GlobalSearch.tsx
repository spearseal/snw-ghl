'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, Loader2, Search, X } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { APP_NAV } from '@/lib/navigation';
import type { SearchResult } from '@/lib/types/common';

interface GlobalSearchProps {
  open: boolean;
  onClose: () => void;
}

export default function GlobalSearch({ open, onClose }: GlobalSearchProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataResults, setDataResults] = useState<SearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);

  const navResults: SearchResult[] = query.trim()
    ? APP_NAV.filter((item) => {
        const q = query.toLowerCase();
        return (
          item.label.toLowerCase().includes(q) ||
          item.keywords?.some((k) => k.includes(q)) ||
          item.description?.toLowerCase().includes(q)
        );
      }).map((item) => ({
        id: item.href,
        type: 'page' as const,
        title: item.label,
        subtitle: item.description,
        href: item.href,
      }))
    : APP_NAV.map((item) => ({
        id: item.href,
        type: 'page' as const,
        title: item.label,
        subtitle: item.description,
        href: item.href,
      }));

  const allResults = [...navResults, ...dataResults];

  const searchData = useCallback(async (q: string) => {
    if (!q.trim()) {
      setDataResults([]);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({ q, limit: '15' });
      const res = await apiFetch(`/api/search?${params.toString()}`);
      if (res.ok) {
        const json = await res.json();
        setDataResults(json.results ?? []);
      }
    } catch {
      setDataResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    setQuery('');
    setDataResults([]);
    setActiveIndex(0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(() => searchData(query), 250);
    return () => clearTimeout(timer);
  }, [query, open, searchData]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, allResults.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === 'Enter' && allResults[activeIndex]) {
        e.preventDefault();
        navigate(allResults[activeIndex]);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, allResults, activeIndex, onClose]);

  const navigate = (result: SearchResult) => {
    if (result.href) {
      router.push(result.href);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[80] flex items-start justify-center bg-black/50 p-4 pt-[10vh] sm:pt-[15vh]"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Global search"
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-slate-200 px-4 dark:border-slate-800">
          <Search className="h-5 w-5 shrink-0 text-slate-400" aria-hidden />
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            placeholder="Search pages, contacts, opportunities…"
            className="flex-1 bg-transparent py-4 text-sm outline-none"
            aria-label="Search"
            autoComplete="off"
          />
          {loading && <Loader2 className="h-4 w-4 animate-spin text-slate-400" aria-hidden />}
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:text-slate-600"
            aria-label="Close search"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <ul className="max-h-[50vh] overflow-y-auto py-2" role="listbox">
          {allResults.length === 0 && !loading && (
            <li className="px-4 py-8 text-center text-sm text-slate-500">No results found</li>
          )}
          {allResults.map((result, index) => (
            <li key={`${result.type}-${result.id}`} role="option" aria-selected={index === activeIndex}>
              <button
                type="button"
                onClick={() => navigate(result)}
                className={`flex w-full items-start gap-3 px-4 py-2.5 text-left text-sm transition ${
                  index === activeIndex
                    ? 'bg-indigo-50 dark:bg-indigo-950/40'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                <div className="min-w-0">
                  <p className="font-medium text-slate-800 dark:text-slate-200">{result.title}</p>
                  {result.subtitle && (
                    <p className="truncate text-xs text-slate-500">{result.subtitle}</p>
                  )}
                  {result.source && (
                    <p className="text-[10px] uppercase text-slate-400">{result.source}</p>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>

        <div className="border-t border-slate-200 px-4 py-2 text-[10px] text-slate-400 dark:border-slate-800">
          ↑↓ navigate · Enter select · Esc close
        </div>
      </div>
    </div>
  );
}
