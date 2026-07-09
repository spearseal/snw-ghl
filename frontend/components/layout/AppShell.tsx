'use client';

import { usePathname, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import TopBar from '@/components/layout/TopBar';
import GlobalSearch from '@/components/layout/GlobalSearch';
import ShortcutsDialog from '@/components/layout/ShortcutsDialog';
import BottomTaskbar, { TaskbarPanel } from '@/components/layout/BottomTaskbar';
import { useKeyboardShortcuts } from '@/hooks/useEnterprise';
import { getToken } from '@/lib/api';
import { isAuthFlowPath, isLoginPath } from '@/lib/routes';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [activePanel, setActivePanel] = useState<TaskbarPanel>(null);
  const [authenticated, setAuthenticated] = useState(
    () => typeof window !== 'undefined' && !!getToken(),
  );
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  useEffect(() => {
    const syncAuth = () => setAuthenticated(!!getToken());
    syncAuth();
    window.addEventListener('session-change', syncAuth);
    return () => window.removeEventListener('session-change', syncAuth);
  }, [pathname]);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const panel = searchParams.get('panel');
    if (panel === 'connectors' || panel === 'email' || panel === 'compliance') {
      setActivePanel(panel);
    }
  }, [searchParams]);

  const toggleSidebar = useCallback(() => {
    setMobileNavOpen((v) => !v);
  }, []);

  useKeyboardShortcuts(
    [
      { key: 'k', meta: true, handler: () => setSearchOpen(true), label: 'Search' },
      { key: 'b', meta: true, handler: toggleSidebar, label: 'Sidebar' },
      { key: 'p', meta: true, handler: () => window.print(), label: 'Print' },
      { key: '?', handler: () => setShortcutsOpen(true), label: 'Shortcuts' },
      { key: 'Escape', handler: () => {
        setSearchOpen(false);
        setShortcutsOpen(false);
        setMobileNavOpen(false);
        setActivePanel(null);
      }},
    ],
    authenticated && !isAuthFlowPath(pathname),
  );

  if (isAuthFlowPath(pathname) || !authenticated) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <Sidebar
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
        onSearchClick={() => setSearchOpen(true)}
      />

      <div className="lg:ml-60">
        <TopBar
          onMenuClick={toggleSidebar}
          onSearchClick={() => setSearchOpen(true)}
          onShortcutsClick={() => setShortcutsOpen(true)}
        />

        <main
          id="main-content"
          className="min-h-screen px-4 pb-20 pt-4 sm:px-6 lg:pb-16 lg:pt-0"
        >
          {children}
        </main>
      </div>

      <BottomTaskbar activePanel={activePanel} onPanelChange={setActivePanel} />
      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
      <ShortcutsDialog open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  );
}
