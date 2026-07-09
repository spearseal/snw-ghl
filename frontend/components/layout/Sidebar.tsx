'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Database, LogOut, Search, ShieldCheck, Snowflake, X } from 'lucide-react';
import { clearSession, getEmail } from '@/lib/api';
import { APP_NAV } from '@/lib/navigation';
import { isActiveNavPath } from '@/lib/routes';
import { cn } from '@/lib/cn';
import { getEmailInitials } from '@/lib/user';

interface SidebarProps {
  mobileOpen: boolean;
  onMobileClose: () => void;
  onSearchClick: () => void;
}

export default function Sidebar({ mobileOpen, onMobileClose, onSearchClick }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const email = getEmail();

  const logout = () => {
    clearSession();
    router.replace('/login');
  };

  const navContent = (
    <>
      <div className="border-b border-border px-5 py-5">
        <Link href="/" className="flex items-center gap-3" onClick={onMobileClose}>
          <div className="flex items-center gap-1 rounded-lg bg-primary-subtle p-2">
            <Database className="h-4 w-4 text-primary" />
            <Snowflake className="h-4 w-4 text-info" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight text-fg">
              Spagent
            </p>
            <p className="flex items-center gap-1 text-caption text-success">
              <ShieldCheck className="h-3 w-3" aria-hidden />
              HIPAA
            </p>
          </div>
        </Link>
      </div>

      <div className="hidden px-3 pt-4 lg:block">
        <button
          type="button"
          onClick={onSearchClick}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-fg-subtle transition-colors duration-fast hover:bg-surface-overlay hover:text-fg"
          aria-label="Open global search"
        >
          <Search className="h-4 w-4" aria-hidden />
          <span>Search…</span>
          <kbd className="ml-auto rounded border border-border px-1.5 text-[10px] text-fg-subtle">
            ⌘K
          </kbd>
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Main navigation">
        {APP_NAV.map(({ href, label, icon: Icon }) => {
          const active = isActiveNavPath(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onMobileClose}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-fast',
                active
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-fg-muted hover:bg-surface-overlay hover:text-fg',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              <span className="truncate">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border p-4">
        {email && (
          <button
            type="button"
            onClick={logout}
            title={`${email} — Log out`}
            aria-label={`Log out (${email})`}
            className="group relative flex h-9 w-9 items-center justify-center rounded-full bg-primary text-xs font-semibold tracking-wide text-white transition-all duration-fast hover:bg-primary-hover"
          >
            <span className="transition-opacity duration-fast group-hover:opacity-0">
              {getEmailInitials(email)}
            </span>
            <LogOut className="absolute h-4 w-4 opacity-0 transition-opacity duration-fast group-hover:opacity-100" aria-hidden />
          </button>
        )}
      </div>
    </>
  );

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          aria-label="Close navigation menu"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 z-50 flex h-screen w-[var(--sidebar-width)] flex-col border-r border-border bg-surface-raised/95 backdrop-blur-md transition-transform duration-200 lg:z-40 lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Sidebar"
      >
        <button
          type="button"
          onClick={onMobileClose}
          className="absolute right-3 top-4 rounded-lg p-1.5 text-fg-muted hover:bg-surface-overlay lg:hidden"
          aria-label="Close menu"
        >
          <X className="h-4 w-4" />
        </button>
        {navContent}
      </aside>
    </>
  );
}
