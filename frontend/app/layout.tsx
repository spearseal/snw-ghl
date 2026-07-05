import type { Metadata } from 'next';
import { Suspense } from 'react';
import AppShell from '@/components/layout/AppShell';
import { ThemeProvider } from '@/components/ThemeProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'GHL + Snowflake Marketing Insights',
  description:
    'Marketing insights dashboard with GoHighLevel and Snowflake data, HIPAA-compliant',
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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <Suspense
            fallback={
              <div className="min-h-screen bg-slate-50 dark:bg-slate-950" />
            }
          >
            <AppShell>{children}</AppShell>
          </Suspense>
        </ThemeProvider>
      </body>
    </html>
  );
}
