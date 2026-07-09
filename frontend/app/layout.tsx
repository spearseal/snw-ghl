import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Suspense } from 'react';
import AppShell from '@/components/layout/AppShell';
import { ThemeProvider } from '@/components/ThemeProvider';
import AppProviders from '@/components/providers/AppProviders';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-sans',
});

export const metadata: Metadata = {
  title: 'Spagent · Revenue Intelligence Platform',
  description:
    'HIPAA-compliant revenue platform: automated upselling, memberships, inventory control, and AI for med spas and clinics',
};

const themeInitScript = `
(function() {
  try {
    var t = localStorage.getItem('ghl_sf_theme');
    if (t === 'light') document.documentElement.classList.remove('dark');
    else document.documentElement.classList.add('dark');
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="font-sans">
        <ThemeProvider>
          <AppProviders>
            <Suspense fallback={<div className="min-h-screen bg-surface" />}>
              <AppShell>{children}</AppShell>
            </Suspense>
          </AppProviders>
        </ThemeProvider>
      </body>
    </html>
  );
}
