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
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-success/10 blur-3xl" />
      </div>

      <div className="absolute right-4 top-4 z-20 sm:right-6 sm:top-6">
        <ThemeToggle showLabel={false} />
      </div>

      <div className="page-container relative z-10 mx-auto max-w-3xl py-12 sm:py-16 lg:py-20">
        {/* Hero */}
        <header className="mb-10 text-center">
          <div className="mb-4 flex justify-center">
            <Badge variant="success">
              <TrendingUp className="mr-1.5 inline h-3.5 w-3.5" aria-hidden />
              Revenue engine · Not another admin line item
            </Badge>
          </div>
          <div className="mb-3 flex items-center justify-center gap-2 text-primary">
            <Sparkles className="h-5 w-5" aria-hidden />
            <span className="text-caption font-medium uppercase tracking-wide">
              Spagent Intelligence
            </span>
          </div>
          <h1 className="text-page-title">
            Turn your data into{' '}
            <span className="text-primary">measurable ROI</span>, not overhead.
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-body">
            GHL + Snowflake intelligence built for med spas and clinics — upsell
            automation, subscription growth, and inventory discipline with HIPAA
            compliance included.
          </p>
        </header>

        {/* Sign in */}
        <Card padding="md" className="mx-auto max-w-md shadow-card">
          <div className="mb-6 text-center">
            <h2 className="text-section-title text-lg">
              {mode === 'login' ? 'Welcome back' : 'Start growing revenue'}
            </h2>
            <p className="mt-1 text-body">
              {mode === 'login'
                ? 'Sign in to access upsell insights, campaigns, and AI queries.'
                : 'Create your account and connect your data sources.'}
            </p>
          </div>

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

            {error && (
              <AlertBanner variant="error" className="mb-0">
                {error}
              </AlertBanner>
            )}

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
        </Card>

        {/* Value props — same page, below sign-in */}
        <section className="mt-12" aria-labelledby="roi-features-heading">
          <h2 id="roi-features-heading" className="mb-6 text-center text-section-title text-base">
            What you get
          </h2>
          <ul className="grid gap-4 sm:grid-cols-2">
            {ROI_FEATURES.map((feature) => (
              <li key={feature.title}>
                <Card hover padding="sm" className="h-full">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="text-card-title">{feature.title}</p>
                      <p className="mt-1 text-caption leading-relaxed">{feature.description}</p>
                    </div>
                    <Badge variant={feature.variant} className="w-fit shrink-0">
                      {feature.metric}
                    </Badge>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
          <p className="mt-8 text-center text-caption">
            Practices using unified CRM + warehouse insights report faster reactivation,
            fewer no-shows, and clearer margin on retail &amp; injectables.
          </p>
        </section>
      </div>
    </main>
  );
}
