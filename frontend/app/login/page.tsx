'use client';

import { LogIn, ShieldCheck, Sparkles, TrendingUp, UserPlus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import ThemeToggle from '@/components/ThemeToggle';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { Card } from '@/components/ui/Card';
import { AlertBanner } from '@/components/ui/PageShell';
import Badge from '@/components/ui/Badge';
import { getToken, setSession } from '@/lib/api';
import { DEFAULT_APP_ROUTE, WELCOME_ROUTE } from '@/lib/routes';

const ROI_FEATURES = [
  {
    title: 'Automated upselling',
    description:
      'Surface treatment gaps and high-intent patients so your team converts more visits into premium services — without extra front-desk labor.',
    metric: '↑ Rev per patient',
    variant: 'success' as const,
  },
  {
    title: 'Membership & subscriptions',
    description:
      'Track recurring plans, renewals, and churn risk in one view. Turn one-time buyers into predictable monthly revenue.',
    metric: '↑ MRR visibility',
    variant: 'primary' as const,
  },
  {
    title: 'Inventory & shrinkage control',
    description:
      'Granular product usage tied to appointments and providers. Catch variance early before margin leaks out the back door.',
    metric: '↓ Shrinkage',
    variant: 'warning' as const,
  },
  {
    title: 'Less front-desk friction',
    description:
      'Spagent AI answers operational questions instantly — schedules, follow-ups, campaigns — so staff stays on revenue work, not admin.',
    metric: '↓ Admin hours',
    variant: 'info' as const,
  },
  {
    title: 'HIPAA-compliant by design',
    description:
      'Encrypted connectors, audit trails, and PHI masking built in. Grow revenue without compliance risk slowing you down.',
    metric: '✓ Audit-ready',
    variant: 'success' as const,
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
    <main className="relative min-h-screen bg-surface">
      <div className="absolute right-4 top-4 z-20 sm:right-6 sm:top-6">
        <ThemeToggle showLabel={false} />
      </div>

      <div className="grid min-h-screen lg:grid-cols-2">
        <section className="relative hidden overflow-hidden border-r border-border bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-10 py-14 lg:flex lg:flex-col lg:justify-between">
          <div className="pointer-events-none absolute -left-24 top-0 h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
          <div className="pointer-events-none absolute bottom-0 right-0 h-64 w-64 rounded-full bg-success/10 blur-3xl" />

          <div className="relative">
            <Badge variant="success" className="mb-6 border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
              <TrendingUp className="mr-1.5 inline h-3.5 w-3.5" />
              Revenue engine
            </Badge>
            <h1 className="max-w-lg text-3xl font-semibold leading-tight tracking-tight text-white xl:text-4xl">
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
              <li key={feature.title}>
                <Card padding="sm" className="border-white/10 bg-white/5 backdrop-blur-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-white">{feature.title}</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-300">
                        {feature.description}
                      </p>
                    </div>
                    <Badge variant={feature.variant} className="shrink-0">
                      {feature.metric}
                    </Badge>
                  </div>
                </Card>
              </li>
            ))}
          </ul>

          <p className="relative mt-8 text-xs text-slate-500">
            Practices using unified CRM + warehouse insights report faster reactivation,
            fewer no-shows, and clearer margin on retail &amp; injectables.
          </p>
        </section>

        <section className="flex flex-col items-center justify-center px-6 py-12 lg:px-12">
          <div className="w-full max-w-md">
            <div className="mb-8 lg:hidden">
              <Badge variant="success" className="mb-2">
                Revenue-generating platform
              </Badge>
              <h1 className="text-page-title">Sign in to your growth dashboard</h1>
            </div>

            <div className="mb-6 hidden lg:block">
              <div className="mb-2 flex items-center gap-2 text-primary">
                <Sparkles className="h-5 w-5" aria-hidden />
                <span className="text-caption font-medium uppercase tracking-wide">
                  Spagent Intelligence
                </span>
              </div>
              <h2 className="text-page-title text-2xl">
                {mode === 'login' ? 'Welcome back' : 'Start growing revenue'}
              </h2>
              <p className="mt-2 text-body">
                {mode === 'login'
                  ? 'Access upsell insights, campaigns, and AI queries.'
                  : 'Create your account and connect your data sources.'}
              </p>
            </div>

            <Card padding="md" className="shadow-card">
              <form onSubmit={submit} className="space-y-4">
                <Input
                  label="Work email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@clinic.com"
                  autoComplete="email"
                />
                <Input
                  label="Password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  helperText="Minimum 8 characters"
                />

                {error && <AlertBanner variant="error" className="mb-0">{error}</AlertBanner>}

                <Button
                  type="submit"
                  loading={loading}
                  className="w-full"
                  size="lg"
                  leftIcon={
                    !loading ? (
                      mode === 'login' ? (
                        <LogIn className="h-5 w-5" aria-hidden />
                      ) : (
                        <UserPlus className="h-5 w-5" aria-hidden />
                      )
                    ) : undefined
                  }
                >
                  {mode === 'login' ? 'Sign in' : 'Create account'}
                </Button>

                <p className="flex items-center justify-center gap-1.5 text-center text-caption">
                  <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden />
                  HIPAA-compliant · encrypted · audit logged
                </p>
              </form>
            </Card>

            <p className="mt-4 text-center text-body">
              {mode === 'login' ? (
                <>
                  New practice?{' '}
                  <button
                    type="button"
                    onClick={() => setMode('register')}
                    className="font-medium text-primary hover:underline"
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
                    className="font-medium text-primary hover:underline"
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
