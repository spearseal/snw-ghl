'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BarChart3,
  Database,
  LogOut,
  Search,
  ShieldCheck,
  Snowflake,
} from 'lucide-react';
import { clearSession, getEmail } from '@/lib/api';

const NAV = [
  { href: '/', label: 'Marketing Insights', icon: BarChart3 },
  { href: '/query', label: 'Query Console', icon: Search },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const email = getEmail();

  const logout = () => {
    clearSession();
    router.push('/login');
  };

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur">
      <div className="border-b border-slate-800 px-5 py-5">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex items-center gap-1 rounded-lg bg-indigo-600/20 p-2">
            <Database className="h-4 w-4 text-indigo-400" />
            <Snowflake className="h-4 w-4 text-sky-400" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">GHL + Snowflake</p>
            <p className="flex items-center gap-1 text-[10px] text-emerald-400">
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
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 p-4">
        {email && (
          <p className="mb-2 truncate text-xs text-slate-500" title={email}>
            {email}
          </p>
        )}
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-slate-900 hover:text-slate-200"
        >
          <LogOut className="h-4 w-4" />
          Log out
        </button>
      </div>
    </aside>
  );
}
