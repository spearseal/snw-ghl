'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BarChart3,
  ClipboardList,
  Database,
  LogOut,
  Sparkles,
  ShieldCheck,
  Snowflake,
} from 'lucide-react';
import ThemeToggle from '@/components/ThemeToggle';
import { clearSession, getEmail } from '@/lib/api';

const NAV = [
  { href: '/ceo-tasks', label: 'CEO Top 5 Tasks', icon: ClipboardList },
  { href: '/', label: 'Marketing Insights', icon: BarChart3 },
  { href: '/query', label: 'Jeans AI', icon: Sparkles },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const email = getEmail();

  const logout = () => {
    clearSession();
    router.replace('/login');
  };

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
      <div className="border-b border-slate-200 px-5 py-5 dark:border-slate-800">
        <Link href="/" className="flex items-center gap-2.5">
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

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                active
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/30'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4 dark:border-slate-800">
        <ThemeToggle className="mb-2 w-full justify-start" />
        {email && (
          <p className="mb-2 truncate text-xs text-slate-500" title={email}>
            {email}
          </p>
        )}
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  );
}
