'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api/auth';
import { signup } from '@/lib/api/signup';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';
import { useAuth } from '@/components/auth/auth-provider';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';

export default function LoginPage() {
  const router = useRouter();
  const { refreshAuth } = useAuth();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);

    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await signup({
          business_name: businessName,
          name,
          email,
          phone,
          password,
        });
        setSuccess('Account created. Redirecting to your workspace...');
      }
    } catch (error: unknown) {
      if (error instanceof ApiError && error.status === 401) {
        setError('Invalid email/password or inactive account.');
        return;
      }

      if (error instanceof ApiError && error.status === 409) {
        setError('That email address is already in use.');
        return;
      }

      if (error instanceof ApiError && error.status >= 500) {
        setError(mode === 'login' ? 'Server error while signing in. Please try again shortly.' : 'Server error while creating your account. Please try again shortly.');
        return;
      }

      if (error instanceof ApiNetworkError) {
        setError(mode === 'login' ? 'Network error while signing in. Check your connection and retry.' : 'Network error while creating your account. Check your connection and retry.');
        return;
      }

      setError(mode === 'login' ? 'Unable to sign in right now. Please try again.' : 'Unable to create your account right now. Please try again.');
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
          <p className="login-eyebrow">EasyEcom Platform</p>
          <div className="login-hero-logo">
            <EasyEcomLogo
              className="easyecom-logo easyecom-logo-hero"
              imageClassName="easyecom-logo-image easyecom-logo-hero"
            />
          </div>
          <h1>Welcome to your operations command center.</h1>
          <p>Monitor inventory, sales, finance, and automation workflows in one premium workspace.</p>
          <div className="login-hero-points">
            <span>Variant-aware stock truth</span>
            <span>Fast operational workflows</span>
            <span>Role-aware business access</span>
          </div>
          <p className="login-hero-signup">
            New to EasyEcom? Create your owner account with a valid business email and start in a fresh tenant workspace.
          </p>
        </section>
        <form className="login-card" onSubmit={onSubmit}>
          <h1 className="login-title">EasyEcom Login</h1>
          <div className="workspace-tabs">
            <button type="button" className={mode === 'login' ? 'workspace-tab active' : 'workspace-tab'} onClick={() => setMode('login')}>
              Sign in
            </button>
            <button type="button" className={mode === 'signup' ? 'workspace-tab active' : 'workspace-tab'} onClick={() => setMode('signup')}>
              Create account
            </button>
          </div>
          <h2>{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
          <p className="muted">
            {mode === 'login'
              ? 'Use your EasyEcom account to continue.'
              : 'Open a new tenant workspace with your business email, owner name, and password.'}
          </p>
          {mode === 'signup' ? (
            <>
              <label>
                Business name
                <input value={businessName} onChange={(event) => setBusinessName(event.target.value)} required disabled={submitting} />
              </label>
              <label>
                Your name
                <input value={name} onChange={(event) => setName(event.target.value)} required disabled={submitting} />
              </label>
              <label>
                Phone
                <input value={phone} onChange={(event) => setPhone(event.target.value)} required disabled={submitting} />
              </label>
            </>
          ) : null}
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
          {success ? <p className="auth-success">{success}</p> : null}
          {error ? <p className="login-error">{error}</p> : null}
          <button type="submit" disabled={submitting}>
            {submitting ? (mode === 'login' ? 'Signing in…' : 'Creating account…') : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </main>
    </AuthRouteGuard>
  );
}
