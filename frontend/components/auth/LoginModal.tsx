'use client';

import { LogIn, ShieldCheck, UserPlus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import { AlertBanner } from '@/components/ui/PageShell';
import { setSession } from '@/lib/api';
import { WELCOME_ROUTE } from '@/lib/routes';

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function LoginModal({ open, onClose, onSuccess }: LoginModalProps) {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetForm = () => {
    setError(null);
    setEmail('');
    setPassword('');
    setMode('login');
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : (data.detail as Array<{ msg: string }>)?.[0]?.msg || `${mode} failed`,
        );
      }
      setSession(data.token as string, data.email as string);
      onSuccess?.();
      router.push(WELCOME_ROUTE);
    } catch (e) {
      setError(e instanceof Error ? e.message : `${mode} failed`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={mode === 'login' ? 'Sign in' : 'Create account'}
      description={
        mode === 'login'
          ? 'Access upsell insights, campaigns, and AI queries.'
          : 'Create your account and connect your data sources.'
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Input
          label="Work email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@clinic.com"
          autoComplete="email"
        />
        <Input
          label="Password"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          helperText="Minimum 8 characters"
        />

        {error && (
          <AlertBanner variant="error" className="mb-0">
            {error}
          </AlertBanner>
        )}

        <Button
          type="submit"
          loading={loading}
          className="w-full"
          size="lg"
          leftIcon={
            !loading ? (
              mode === 'login' ? (
                <LogIn className="h-5 w-5" aria-hidden />
              ) : (
                <UserPlus className="h-5 w-5" aria-hidden />
              )
            ) : undefined
          }
        >
          {mode === 'login' ? 'Sign in' : 'Create account'}
        </Button>

        <p className="flex items-center justify-center gap-1.5 text-center text-caption">
          <ShieldCheck className="h-3.5 w-3.5 text-success" aria-hidden />
          HIPAA-compliant · encrypted · audit logged
        </p>
      </form>

      <p className="mt-4 text-center text-body">
        {mode === 'login' ? (
          <>
            New practice?{' '}
            <button
              type="button"
              onClick={() => {
                setMode('register');
                setError(null);
              }}
              className="font-medium text-primary hover:underline"
            >
              Register
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button
              type="button"
              onClick={() => {
                setMode('login');
                setError(null);
              }}
              className="font-medium text-primary hover:underline"
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </Modal>
  );
}
