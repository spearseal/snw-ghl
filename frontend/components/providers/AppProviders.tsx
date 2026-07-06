'use client';

import type { ReactNode } from 'react';
import { ToastProvider } from '@/components/providers/ToastProvider';
import { ConfirmProvider } from '@/components/providers/ConfirmProvider';
import ErrorBoundary from '@/components/ui/ErrorBoundary';

export default function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <ErrorBoundary>{children}</ErrorBoundary>
      </ConfirmProvider>
    </ToastProvider>
  );
}
