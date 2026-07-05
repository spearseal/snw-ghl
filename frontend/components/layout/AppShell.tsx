'use client';

import { usePathname, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import BottomTaskbar, { TaskbarPanel } from '@/components/layout/BottomTaskbar';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activePanel, setActivePanel] = useState<TaskbarPanel>(null);

  useEffect(() => {
    const panel = searchParams.get('panel');
    if (panel === 'connectors' || panel === 'email' || panel === 'compliance') {
      setActivePanel(panel);
    }
  }, [searchParams]);

  if (pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <Sidebar />
      <main className="ml-60 min-h-screen pb-16 pr-6 pl-6 pt-6">{children}</main>
      <BottomTaskbar activePanel={activePanel} onPanelChange={setActivePanel} />
    </div>
  );
}
