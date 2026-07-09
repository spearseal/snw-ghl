'use client';

import { LogIn, Sparkles, TrendingUp } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginModal from '@/components/auth/LoginModal';
import ThemeToggle from '@/components/ThemeToggle';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { getToken } from '@/lib/api';
import { DEFAULT_APP_ROUTE } from '@/lib/routes';

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
  const [loginOpen, setLoginOpen] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace(DEFAULT_APP_ROUTE);
    }
  }, [router]);

  return (
    <main className="relative min-h-screen bg-surface">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-success/10 blur-3xl" />
      </div>

      <div className="absolute right-4 top-4 z-20 flex items-center gap-2 sm:right-6 sm:top-6">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setLoginOpen(true)}
          leftIcon={<LogIn className="h-4 w-4" aria-hidden />}
        >
          Log in
        </Button>
        <ThemeToggle showLabel={false} />
      </div>

      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />

      <div className="page-container relative z-10 mx-auto max-w-3xl py-12 sm:py-16 lg:py-20">
        <header className="mb-12 text-center">
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

        <section aria-labelledby="roi-features-heading">
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
