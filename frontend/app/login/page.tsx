'use client';

import { useRouter } from 'next/navigation';
import { FormEvent, useState } from 'react';
import { apiPost } from '../../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const user = await apiPost('/auth/login', { email, password }, null);
      localStorage.setItem('easy_ecom_user', JSON.stringify(user));
      router.push('/dashboard');
    } catch {
      setError('Invalid credentials');
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ maxWidth: 320, margin: '60px auto' }}>
      <h1>Login</h1>
      <input aria-label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input aria-label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button type="submit">Login</button>
      {error ? <p>{error}</p> : null}
    </form>
  );
}
