'use client';
import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api/auth';

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
      router.replace('/dashboard');
    } catch {
      setError('Invalid email/password or inactive account.');
    }
  };

  return <main className="login-page"><form className="login-card" onSubmit={onSubmit}><h1>EasyEcom Login</h1><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>{error ? <p className="login-error">{error}</p> : null}<button type="submit">Sign in</button></form></main>;
}
