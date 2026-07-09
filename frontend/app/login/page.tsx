'use client';

import {
  Loader2,
  LogIn,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserPlus,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import ThemeToggle from '@/components/ThemeToggle';
import { getToken, setSession } from '@/lib/api';
import { DEFAULT_APP_ROUTE, WELCOME_ROUTE } from '@/lib/routes';

const ROI_FEATURES = [
  {
    title: 'Automated upselling',
    description:
      'Surface treatment gaps and high-intent patients so your team converts more visits into premium services — without extra front-desk labor.',
    metric: '↑ Rev per patient',
    accent: 'from-emerald-500/20 to-teal-500/10',
    border: 'border-emerald-500/30',
  },
  {
    title: 'Membership & subscriptions',
    description:
      'Track recurring plans, renewals, and churn risk in one view. Turn one-time buyers into predictable monthly revenue.',
    metric: '↑ MRR visibility',
    accent: 'from-indigo-500/20 to-violet-500/10',
    border: 'border-indigo-500/30',
  },
  {
    title: 'Inventory & shrinkage control',
    description:
      'Granular product usage tied to appointments and providers. Catch variance early before margin leaks out the back door.',
    metric: '↓ Shrinkage',
    accent: 'from-amber-500/20 to-orange-500/10',
    border: 'border-amber-500/30',
  },
  {
    title: 'Less front-desk friction',
    description:
      'Spagent AI answers operational questions instantly — schedules, follow-ups, campaigns — so staff stays on revenue work, not admin.',
    metric: '↓ Admin hours',
    accent: 'from-sky-500/20 to-cyan-500/10',
    border: 'border-sky-500/30',
  },
  {
    title: 'HIPAA-compliant by design',
    description:
      'Encrypted connectors, audit trails, and PHI masking built in. Grow revenue without compliance risk slowing you down.',
    metric: '✓ Audit-ready',
    accent: 'from-emerald-500/15 to-slate-500/10',
    border: 'border-emerald-600/25',
  },
] as const;

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getToken()) {
      router.replace(DEFAULT_APP_ROUTE);
    }
  }, [router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : (data.detail as Array<{ msg: string }>)?.[0]?.msg || `${mode} failed`,
        );
      }
      setSession(data.token as string, data.email as string);
      router.push(WELCOME_ROUTE);
    } catch (e) {
      setError(e instanceof Error ? e.message : `${mode} failed`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="relative min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="absolute right-4 top-4 z-20 sm:right-6 sm:top-6">
        <ThemeToggle showLabel={false} />
      </div>

      <div className="grid min-h-screen lg:grid-cols-2">
        {/* Revenue pitch — not an admin tool */}
        <section className="relative hidden overflow-hidden border-r border-slate-200 bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-10 py-14 lg:flex lg:flex-col lg:justify-between dark:border-slate-800">
          <div className="pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="pointer-events-none absolute bottom-0 right-0 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />

          <div className="relative">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wider text-emerald-300">
              <TrendingUp className="h-3.5 w-3.5" />
              Revenue engine · Not another admin line item
            </div>
            <h1 className="max-w-lg text-3xl font-bold leading-tight tracking-tight text-white xl:text-4xl">
              Turn your data into{' '}
              <span className="bg-gradient-to-r from-emerald-300 to-indigo-300 bg-clip-text text-transparent">
                measurable ROI
              </span>
              , not overhead.
            </h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-300">
              GHL + Snowflake intelligence built for med spas and clinics that want
              upsell automation, subscription growth, and inventory discipline — with
              HIPAA compliance included.
            </p>
          </div>

          <ul className="relative mt-10 space-y-3">
            {ROI_FEATURES.map((feature) => (
              <li
                key={feature.title}
                className={`rounded-xl border bg-gradient-to-r ${feature.accent} ${feature.border} p-4 backdrop-blur-sm`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-white">{feature.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-300">
                      {feature.description}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-md bg-white/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-200">
                    {feature.metric}
                  </span>
                </div>
              </li>
            ))}
          </ul>

          <p className="relative mt-8 text-xs text-slate-500">
            Practices using unified CRM + warehouse insights report faster reactivation,
            fewer no-shows, and clearer margin on retail &amp; injectables.
          </p>
        </section>

        {/* Login form */}
        <section className="flex flex-col items-center justify-center px-6 py-12 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-8 lg:hidden">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
                <TrendingUp className="h-3.5 w-3.5" />
                Revenue-generating platform
              </div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
                Sign in to your growth dashboard
              </h1>
            </div>

            <div className="mb-6 hidden lg:block">
              <div className="mb-2 flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                <Sparkles className="h-5 w-5" />
                <span className="text-sm font-semibold uppercase tracking-wide">
                  Spagent Intelligence
                </span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
                {mode === 'login' ? 'Welcome back' : 'Start growing revenue'}
              </h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                {mode === 'login'
                  ? 'Access upsell insights, campaigns, and AI queries.'
                  : 'Create your account and connect your data sources.'}
              </p>
            </div>

            <form
              onSubmit={submit}
              className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900/80"
            >
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Work email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@clinic.com"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Password
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 text-slate-900 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-3 font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : mode === 'login' ? (
                  <LogIn className="h-5 w-5" />
                ) : (
                  <UserPlus className="h-5 w-5" />
                )}
                {mode === 'login' ? 'Sign in' : 'Create account'}
              </button>

              <p className="flex items-center justify-center gap-1.5 text-center text-xs text-slate-500">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                HIPAA-compliant · encrypted · audit logged
              </p>
            </form>

            <p className="mt-4 text-center text-sm text-slate-600 dark:text-slate-400">
              {mode === 'login' ? (
                <>
                  New practice?{' '}
                  <button
                    type="button"
                    onClick={() => setMode('register')}
                    className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                  >
                    Register
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => setMode('login')}
                    className="font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                  >
                    Sign in
                  </button>
                </>
              )}
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
