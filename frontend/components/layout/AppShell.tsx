'use client';

import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import BottomTaskbar, { TaskbarPanel } from '@/components/layout/BottomTaskbar';
import { getToken } from '@/lib/api';
import { isLoginPath } from '@/lib/routes';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activePanel, setActivePanel] = useState<TaskbarPanel>(null);
  const [authenticated, setAuthenticated] = useState(
    () => typeof window !== 'undefined' && !!getToken()
  );

  useEffect(() => {
    const syncAuth = () => setAuthenticated(!!getToken());
    syncAuth();
    window.addEventListener('session-change', syncAuth);
    return () => window.removeEventListener('session-change', syncAuth);
  }, [pathname]);

  useEffect(() => {
    const panel = searchParams.get('panel');
    if (panel === 'connectors' || panel === 'email' || panel === 'compliance') {
      setActivePanel(panel);
    }
  }, [searchParams]);

  if (isLoginPath(pathname) || !authenticated) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <main className="ml-60 min-h-screen pb-16 pr-6 pl-6 pt-6">{children}</main>
      <BottomTaskbar activePanel={activePanel} onPanelChange={setActivePanel} />
    </div>
  );
}
