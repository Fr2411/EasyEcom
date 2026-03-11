'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api/auth';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';
import { useAuth } from '@/components/auth/auth-provider';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

export default function LoginPage() {
  const router = useRouter();
  const { refreshAuth } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await login(email, password);
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        setError('Invalid email/password or inactive account.');
        return;
      }

      if (error instanceof ApiError && error.status >= 500) {
        setError('Server error while signing in. Please try again shortly.');
        return;
      }

      if (error instanceof ApiNetworkError) {
        setError('Network error while signing in. Check your connection and retry.');
        return;
      }

      setError('Unable to sign in right now. Please try again.');
      return;
    } finally {
      setSubmitting(false);
    }

    await refreshAuth();
    router.replace('/dashboard');
  };

  return (
    <AuthRouteGuard mode="public-only">
      <main className="login-page">
        <section className="login-hero">
          <p className="eyebrow">EasyEcom</p>
          <h1>Welcome to your operations command center.</h1>
          <p>Monitor inventory, sales, finance, and automation workflows in one premium workspace.</p>
        </section>
        <form className="login-card" onSubmit={onSubmit}>
          <h1 className="login-title">EasyEcom Login</h1>
          <h2>Sign in</h2>
          <p className="muted">Use your EasyEcom account to continue.</p>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required disabled={submitting} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              disabled={submitting}
            />
          </label>
          {error ? <p className="login-error">{error}</p> : null}
          <button type="submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
        </form>
      </main>
    </AuthRouteGuard>
  );
}
