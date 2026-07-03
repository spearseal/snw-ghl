'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Database, Loader2, LogIn, ShieldCheck, Snowflake, UserPlus } from 'lucide-react';
import { setSession } from '@/lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      let res: Response;
      try {
        res = await fetch(`/api/auth/${mode}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
      } catch {
        throw new Error('Network error — could not reach the server. Please check your connection and try again.');
      }

      let data: Record<string, unknown>;
      try {
        data = await res.json();
      } catch {
        throw new Error(`Server returned an unexpected response (HTTP ${res.status}). Please try again.`);
      }

      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : (data.detail as Array<{ msg: string }>)?.[0]?.msg || `${mode} failed`
        );
      }
      setSession(data.token as string, data.email as string);
      router.push('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : `${mode} failed`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mb-3 inline-flex items-center gap-1 rounded-xl bg-indigo-600/20 p-3">
            <Database className="h-6 w-6 text-indigo-400" />
            <Snowflake className="h-6 w-6 text-sky-400" />
          </div>
          <h1 className="text-xl font-semibold">
            {mode === 'login' ? 'Sign in' : 'Create your account'}
          </h1>
          <p className="mt-1 flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
            HIPAA-compliant query console
          </p>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6"
        >
          <div>
            <label className="mb-1.5 block text-sm text-slate-400">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@clinic.com"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-slate-100 placeholder-slate-600 outline-none transition focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm text-slate-400">
              Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-slate-100 placeholder-slate-600 outline-none transition focus:border-indigo-500"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-800/60 bg-red-950/40 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : mode === 'login' ? (
              <LogIn className="h-5 w-5" />
            ) : (
              <UserPlus className="h-5 w-5" />
            )}
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          {mode === 'login' ? (
            <>
              No account?{' '}
              <button
                onClick={() => setMode('register')}
                className="text-indigo-400 hover:underline"
              >
                Register
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                onClick={() => setMode('login')}
                className="text-indigo-400 hover:underline"
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </main>
  );
}
