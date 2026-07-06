'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Database, LogOut, Search, ShieldCheck, Snowflake, X } from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
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
      <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-800">
        <Link href="/" className="flex items-center gap-2.5" onClick={onMobileClose}>
          <div className="flex items-center gap-1 rounded-lg bg-indigo-600/20 p-2">
            <Database className="h-4 w-4 text-indigo-500 dark:text-indigo-400" />
            <Snowflake className="h-4 w-4 text-sky-500 dark:text-sky-400" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-slate-900 dark:text-slate-100">
              GHL + Snowflake
            </p>
            <p className="flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-3 w-3" />
              HIPAA
            </p>
          </div>
        </Link>
      </div>

      <div className="hidden px-3 pt-4 lg:block">
        <button
          type="button"
          onClick={onSearchClick}
          className="flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
          aria-label="Open global search"
        >
          <Search className="h-4 w-4" />
          <span>Search…</span>
          <kbd className="ml-auto rounded border border-slate-300 px-1.5 text-[10px] dark:border-slate-600">
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
                'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition',
                active
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/30'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4 dark:border-slate-800">
        <ThemeToggle className="mb-2 w-full justify-start" />
        {email && (
          <div
            className="mb-3 flex items-center gap-2"
            title={email}
            aria-label={`Signed in as ${email}`}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold tracking-wide text-white">
              {getEmailInitials(email)}
            </span>
          </div>
        )}
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Log out
        </button>
      </div>
    </>
  );

  return (
    <>
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          aria-label="Close navigation menu"
          onClick={onMobileClose}
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 z-50 flex h-screen w-60 flex-col border-r border-slate-200 bg-white/95 backdrop-blur transition-transform duration-200 dark:border-slate-800 dark:bg-slate-950/95 lg:z-40 lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Sidebar"
      >
        <button
          type="button"
          onClick={onMobileClose}
          className="absolute right-3 top-4 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 lg:hidden dark:hover:bg-slate-800"
          aria-label="Close menu"
        >
          <X className="h-4 w-4" />
        </button>
        {navContent}
      </aside>
    </>
  );
}
