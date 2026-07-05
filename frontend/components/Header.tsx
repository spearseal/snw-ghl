'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Cable, Database, LogOut, Search, ShieldCheck, Snowflake } from 'lucide-react';
import { clearSession, getEmail, getToken } from '@/lib/api';
import { isLoginPath } from '@/lib/routes';

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    setEmail(getToken() ? getEmail() : null);
  }, [pathname]);

  if (isLoginPath(pathname)) return null;

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  const navClass = (href: string) =>
    `flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition ${
      pathname === href
        ? 'bg-indigo-600 text-white'
        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
    }`;

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex items-center gap-1 rounded-lg bg-indigo-600/20 p-1.5">
            <Database className="h-4 w-4 text-indigo-400" />
            <Snowflake className="h-4 w-4 text-sky-400" />
          </div>
          <span className="font-semibold">GHL + Snowflake</span>
          <span className="ml-1 hidden items-center gap-1 rounded-full border border-emerald-700/50 bg-emerald-900/30 px-2 py-0.5 text-[10px] text-emerald-300 sm:flex">
            <ShieldCheck className="h-3 w-3" />
            HIPAA
          </span>
        </Link>

        <nav className="flex items-center gap-2">
          <Link href="/" className={navClass('/')}>
            <Search className="h-4 w-4" />
            Query
          </Link>
          <Link href="/connectors" className={navClass('/connectors')}>
            <Cable className="h-4 w-4" />
            DB Connectors
          </Link>

          {email && (
            <>
              <span className="ml-2 hidden max-w-[160px] truncate text-xs text-slate-500 md:block">
                {email}
              </span>
              <button
                onClick={logout}
                title="Log out"
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400 transition hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
