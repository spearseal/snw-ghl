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
import Button from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { getEmail, getToken } from '@/lib/api';
import { DEFAULT_APP_ROUTE } from '@/lib/routes';
import { getDisplayNameFromEmail, getEmailInitials } from '@/lib/user';

const QUICK_WINS = [
  { icon: TrendingUp, label: 'Reactivate & upsell', href: '/reactivate-campaign', color: 'text-success' },
  { icon: Repeat, label: 'Revenue & memberships', href: '/revenue-growth', color: 'text-primary' },
  { icon: Package, label: 'Treatment & inventory', href: '/treatment-plans', color: 'text-warning' },
  { icon: Sparkles, label: 'Spagent AI', href: '/query', color: 'text-info' },
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
      <div className="flex min-h-screen items-center justify-center bg-surface">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const displayName = getDisplayNameFromEmail(email);
  const initials = getEmailInitials(email);

  return (
    <main className="relative min-h-screen bg-gradient-to-b from-surface via-surface-raised to-primary-subtle/30">
      <div className="absolute right-4 top-4 z-10 sm:right-6 sm:top-6">
        <ThemeToggle showLabel={false} />
      </div>

      <div className="page-container-narrow flex min-h-screen flex-col items-center justify-center py-16">
        <div className="mb-8 flex h-20 w-20 items-center justify-center rounded-full bg-primary text-2xl font-semibold text-white shadow-card-hover">
          {initials}
        </div>

        <p className="text-caption font-medium uppercase tracking-widest text-primary">
          You&apos;re in
        </p>
        <h1 className="mt-2 text-center text-page-title">
          Welcome, {displayName}
        </h1>
        <p className="mt-2 text-center text-body">{email}</p>

        <p className="mt-6 max-w-lg text-center text-body">
          Your revenue dashboard is ready. Use the tools below to grow MRR, reduce
          shrinkage, and cut front-desk busywork — all under{' '}
          <span className="inline-flex items-center gap-1 font-medium text-success">
            <ShieldCheck className="h-4 w-4" aria-hidden />
            HIPAA compliance
          </span>
          .
        </p>

        <div className="mt-10 grid w-full gap-3 sm:grid-cols-2">
          {QUICK_WINS.map(({ icon: Icon, label, href, color }) => (
            <Link key={href} href={href} className="group">
              <Card hover padding="sm" className="flex items-center gap-3">
                <Icon className={`h-5 w-5 shrink-0 ${color}`} aria-hidden />
                <span className="text-sm font-medium text-fg group-hover:text-primary">{label}</span>
              </Card>
            </Link>
          ))}
        </div>

        <Link href={DEFAULT_APP_ROUTE} className="mt-10">
          <Button
            size="lg"
            leftIcon={<Users className="h-5 w-5" aria-hidden />}
            rightIcon={<ArrowRight className="h-5 w-5" aria-hidden />}
          >
            Enter Spagent AI
          </Button>
        </Link>

        <p className="mt-6 text-center text-caption">
          This platform pays for itself through upsell automation, subscription
          retention, and inventory control — not admin hours.
        </p>
      </div>
    </main>
  );
}
