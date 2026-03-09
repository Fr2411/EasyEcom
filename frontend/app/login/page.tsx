'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, login } from '@/lib/api/auth';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';
import { ApiError, ApiNetworkError } from '@/lib/api/client';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await login(email, password);
      await getCurrentUser();
      router.replace('/dashboard');
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
    }
  };

  return (
    <AuthRouteGuard mode="public-only">
      <main className="login-page"><form className="login-card" onSubmit={onSubmit}><h1>EasyEcom Login</h1><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{error ? <p className="login-error">{error}</p> : null}<button type="submit">Sign in</button></form></main>
    </AuthRouteGuard>
  );
}
