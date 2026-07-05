import type { Metadata } from 'next';
import { Suspense } from 'react';
import AppShell from '@/components/layout/AppShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'GHL + Snowflake Marketing Insights',
  description:
    'Marketing insights dashboard with GoHighLevel and Snowflake data, HIPAA-compliant',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
          <AppShell>{children}</AppShell>
        </Suspense>
      </body>
    </html>
  );
}
