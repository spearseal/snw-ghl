'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  message?: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, message: undefined });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="flex min-h-[40vh] flex-col items-center justify-center px-6 text-center"
          role="alert"
        >
          <AlertTriangle className="mb-4 h-10 w-10 text-amber-500" aria-hidden />
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
            {this.props.fallbackTitle ?? 'Something went wrong'}
          </h2>
          <p className="mt-2 max-w-md text-sm text-slate-600 dark:text-slate-400">
            {this.state.message ?? 'An unexpected error occurred. Please try again.'}
          </p>
          <button
            type="button"
            onClick={this.handleRetry}
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
