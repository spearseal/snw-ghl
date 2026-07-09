'use client';

import {
  ArrowRight,
  Package,
  Repeat,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import ThemeToggle from '@/components/ThemeToggle';
import { getEmail, getToken } from '@/lib/api';
import { DEFAULT_APP_ROUTE } from '@/lib/routes';
import { getDisplayNameFromEmail, getEmailInitials } from '@/lib/user';

const QUICK_WINS = [
  {
    icon: TrendingUp,
    label: 'Reactivate & upsell',
    href: '/reactivate-campaign',
    color: 'text-emerald-600 dark:text-emerald-400',
  },
  {
    icon: Repeat,
    label: 'Revenue & memberships',
    href: '/revenue-growth',
    color: 'text-indigo-600 dark:text-indigo-400',
  },
  {
    icon: Package,
    label: 'Treatment & inventory',
    href: '/treatment-plans',
    color: 'text-amber-600 dark:text-amber-400',
  },
  {
    icon: Sparkles,
    label: 'Spagent AI',
    href: '/query',
    color: 'text-violet-600 dark:text-violet-400',
  },
] as const;

export default function WelcomePage() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    setEmail(getEmail());
  }, [router]);

  if (!email) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
      </div>
    );
  }

  const displayName = getDisplayNameFromEmail(email);
  const initials = getEmailInitials(email);

  return (
    <main className="relative min-h-screen bg-gradient-to-b from-slate-50 via-white to-indigo-50/30 dark:from-slate-950 dark:via-slate-950 dark:to-indigo-950/20">
      <div className="absolute right-4 top-4 z-10 sm:right-6 sm:top-6">
        <ThemeToggle showLabel={false} />
      </div>

      <div className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center px-6 py-16">
        <div className="mb-8 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-2xl font-bold text-white shadow-lg shadow-indigo-500/30">
          {initials}
        </div>

        <p className="text-sm font-medium uppercase tracking-widest text-indigo-600 dark:text-indigo-400">
          You&apos;re in
        </p>
        <h1 className="mt-2 text-center text-3xl font-bold text-slate-900 dark:text-slate-50 sm:text-4xl">
          Welcome, {displayName}
        </h1>
        <p className="mt-2 text-center text-sm text-slate-600 dark:text-slate-400">{email}</p>

        <p className="mt-6 max-w-lg text-center text-base leading-relaxed text-slate-700 dark:text-slate-300">
          Your revenue dashboard is ready. Use the tools below to grow MRR, reduce
          shrinkage, and cut front-desk busywork — all under{' '}
          <span className="inline-flex items-center gap-1 font-medium text-emerald-700 dark:text-emerald-400">
            <ShieldCheck className="h-4 w-4" />
            HIPAA compliance
          </span>
          .
        </p>

        <div className="mt-10 grid w-full gap-3 sm:grid-cols-2">
          {QUICK_WINS.map(({ icon: Icon, label, href, color }) => (
            <Link
              key={href}
              href={href}
              className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-800 shadow-sm transition hover:border-indigo-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-indigo-700"
            >
              <Icon className={`h-5 w-5 shrink-0 ${color}`} />
              {label}
            </Link>
          ))}
        </div>

        <Link
          href={DEFAULT_APP_ROUTE}
          className="mt-10 inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-indigo-600/25 transition hover:bg-indigo-500"
        >
          <Users className="h-5 w-5" />
          Enter Spagent AI
          <ArrowRight className="h-5 w-5" />
        </Link>

        <p className="mt-6 text-center text-xs text-slate-500">
          This platform pays for itself through upsell automation, subscription
          retention, and inventory control — not admin hours.
        </p>
      </div>
    </main>
  );
}
