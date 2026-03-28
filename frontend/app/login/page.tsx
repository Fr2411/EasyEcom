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
          <div className="login-hero-content">
            <p className="login-eyebrow">EasyEcom Commerce OS</p>
            <div className="login-hero-logo">
              <EasyEcomLogo
                className="easyecom-logo easyecom-logo-hero"
                imageClassName="easyecom-logo-image easyecom-logo-hero"
              />
            </div>
            <h1>Run inventory, sales, returns, and finance from one cleaner workspace.</h1>
            <p>
              EasyEcom is built for operational teams who need trustworthy stock, faster order handling,
              and clearer day-to-day control across the business.
            </p>
            <div className="login-hero-points">
              <span>Variant-aware stock truth</span>
              <span>Tenant-safe team access</span>
              <span>Operational dashboards</span>
            </div>
            <div className="login-hero-proof-grid" aria-label="Platform highlights">
              <div className="login-proof-card">
                <strong>Live operations</strong>
                <p>Track sales, inventory, returns, and reviews without switching tools.</p>
              </div>
              <div className="login-proof-card">
                <strong>Faster onboarding</strong>
                <p>Open a workspace with business identity first, then grow into advanced modules.</p>
              </div>
              <div className="login-proof-card">
                <strong>Commerce-ready controls</strong>
                <p>Purpose-built for merchants, not a generic back-office template.</p>
              </div>
            </div>
          </div>
        </section>
        <form className="login-card" onSubmit={onSubmit}>
          <h1 className="login-title">EasyEcom Login</h1>
          <div className="login-card-header">
            <div>
              <p className="login-card-kicker">{mode === 'login' ? 'Welcome back' : 'Start your workspace'}</p>
              <h2>{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
              <p className="muted login-card-subtitle">
                {mode === 'login'
                  ? 'Use your EasyEcom account to continue into your business workspace.'
                  : 'Create a new tenant workspace with a valid business email and owner details.'}
              </p>
            </div>
            <div className="workspace-tabs" aria-label="Authentication mode">
              <button type="button" className={mode === 'login' ? 'workspace-tab active' : 'workspace-tab'} onClick={() => setMode('login')}>
                Sign in
              </button>
              <button type="button" className={mode === 'signup' ? 'workspace-tab active' : 'workspace-tab'} onClick={() => setMode('signup')}>
                Create account
              </button>
            </div>
          </div>
          <div className="login-card-section">
            <div className="login-card-note">
              <strong>{mode === 'login' ? 'Returning user' : 'New tenant'}</strong>
              <span>
                {mode === 'login'
                  ? 'Access your existing operational workspace.'
                  : 'Your signup creates an owner account and a fresh tenant workspace.'}
              </span>
            </div>
          </div>
          {mode === 'signup' ? (
            <div className="login-form-grid login-form-grid-signup">
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
              <label>
                Email
                <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required disabled={submitting} />
              </label>
              <label className="login-form-field-full">
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  disabled={submitting}
                />
              </label>
            </div>
          ) : (
            <div className="login-form-grid">
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
            </div>
          )}
          <div className="login-card-status">
            {success ? <p className="auth-success">{success}</p> : null}
            {error ? <p className="login-error">{error}</p> : null}
          </div>
          <div className="login-card-actions">
            <button type="submit" disabled={submitting}>
              {submitting ? (mode === 'login' ? 'Signing in…' : 'Creating account…') : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
            <p className="login-card-footnote">
              {mode === 'login'
                ? 'Use the owner or assigned team credentials for this workspace.'
                : 'Only valid business emails should be used for new tenant creation.'}
            </p>
          </div>
        </form>
      </main>
    </AuthRouteGuard>
  );
}
