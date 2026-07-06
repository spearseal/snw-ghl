'use client';

import { Menu, Search } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';

interface TopBarProps {
  onMenuClick: () => void;
  onSearchClick: () => void;
  onShortcutsClick: () => void;
}

export default function TopBar({ onMenuClick, onSearchClick, onShortcutsClick }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-slate-200 bg-white/95 px-4 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-950/95 print:hidden">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
        aria-label="Open navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <button
        type="button"
        onClick={onSearchClick}
        className="flex flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900"
        aria-label="Open global search"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span>Search…</span>
        <kbd className="ml-auto hidden rounded border border-slate-300 px-1.5 text-[10px] sm:inline dark:border-slate-600">
          ⌘K
        </kbd>
      </button>

      <button
        type="button"
        onClick={onShortcutsClick}
        className="rounded-lg p-2 text-xs font-medium text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts"
      >
        ?
      </button>

      <ThemeToggle showLabel={false} />
    </header>
  );
}
