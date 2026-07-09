'use client';

import { Menu, Search } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import Button from '@/components/ui/Button';

interface TopBarProps {
  onMenuClick: () => void;
  onSearchClick: () => void;
  onShortcutsClick: () => void;
}

export default function TopBar({ onMenuClick, onSearchClick, onShortcutsClick }: TopBarProps) {
  return (
    <header
      className="sticky top-0 z-30 flex h-[var(--header-height)] items-center gap-2 border-b border-border bg-surface-raised/90 px-4 shadow-header backdrop-blur-md sm:px-6 print:hidden"
      role="banner"
    >
      <Button
        variant="ghost"
        size="sm"
        onClick={onMenuClick}
        className="lg:hidden"
        aria-label="Open navigation menu"
        leftIcon={<Menu className="h-5 w-5" />}
      />

      <button
        type="button"
        onClick={onSearchClick}
        className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-left text-sm text-fg-subtle transition-colors duration-fast hover:border-primary/30 hover:bg-surface-overlay lg:max-w-sm lg:flex-none"
        aria-label="Open global search"
      >
        <Search className="h-4 w-4 shrink-0" aria-hidden />
        <span className="hidden truncate sm:inline">Search pages and actions…</span>
        <kbd className="ml-auto hidden shrink-0 rounded border border-border px-1.5 text-[10px] text-fg-subtle sm:inline">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={onShortcutsClick}
          aria-label="Keyboard shortcuts"
          title="Keyboard shortcuts"
        >
          ?
        </Button>
        <ThemeToggle showLabel={false} />
      </div>
    </header>
  );
}
