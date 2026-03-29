'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AuthCard } from '@/components/auth/auth-card';
import { FormInput } from '@/components/auth/form-input';
import { useAuth } from '@/components/auth/auth-provider';
import { AuthLayout } from '@/components/layout/auth-layout';
import { ApiError, ApiNetworkError } from '@/lib/api/client';
import { login } from '@/lib/api/auth';
import { signup } from '@/lib/api/signup';
import { PrimaryButton } from '@/components/ui/primary-button';
import { SecondaryButton } from '@/components/ui/secondary-button';

type AuthMode = 'login' | 'signup';

type FieldErrors = {
  name?: string;
  businessName?: string;
  email?: string;
  password?: string;
};

function validateEmail(value: string) {
  return /\S+@\S+\.\S+/.test(value);
}

function validateForm(mode: AuthMode, fields: { name: string; businessName: string; email: string; password: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (mode === 'signup' && !fields.name.trim()) errors.name = 'Full name is required.';
  if (mode === 'signup' && !fields.businessName.trim()) errors.businessName = 'Business name is required.';
  if (!fields.email.trim()) errors.email = 'Email is required.';
  else if (!validateEmail(fields.email)) errors.email = 'Enter a valid email address.';
  if (!fields.password.trim()) errors.password = 'Password is required.';
  else if (mode === 'signup' && fields.password.length < 8) errors.password = 'Password must be at least 8 characters.';
  return errors;
}

export function AuthPageView({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const { user, loading, refreshAuth } = useAuth();
  const [name, setName] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  useEffect(() => {
    if (!loading && user) {
      router.replace('/dashboard');
    }
  }, [loading, router, user]);

  const content = useMemo(() => {
    if (mode === 'login') {
      return {
        eyebrow: 'Welcome back',
        title: 'Welcome back',
        description: 'Sign in to your EasyEcom workspace and manage your sales, inventory, and operations in one place.',
        heroTitle: 'Keep sales, stock, and daily operations under control.',
        heroDescription: 'EasyEcom helps growing businesses reply faster, stay organized, and turn customer conversations into real orders without adding operational chaos.',
        points: [
          'Reply to customers faster',
          'Track stock with confidence',
          'Keep orders and operations organized',
        ],
      };
    }

    return {
      eyebrow: 'Create account',
      title: 'Create your EasyEcom account',
      description: 'Start free and set up your business in minutes.',
      heroTitle: 'Set up a smarter business system from day one.',
      heroDescription: 'Create your workspace, add your products, and start managing customer conversations, inventory, and sales from one place.',
      points: [
        'Start free with no card required',
        'Set up products and business details quickly',
        'Grow without adding more chaos',
      ],
    };
  }, [mode]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validateForm(mode, { name, businessName, email, password });
    setFieldErrors(nextErrors);
    setError('');
    if (Object.keys(nextErrors).length) {
      return;
    }

    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await signup({
          name,
          business_name: businessName,
          email,
          phone: '',
          password,
        });
      }
      await refreshAuth();
      router.replace('/dashboard');
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.status === 401) {
        setError('Invalid email or password.');
      } else if (loadError instanceof ApiError && loadError.status === 409) {
        setError('That email address is already in use.');
      } else if (loadError instanceof ApiNetworkError) {
        setError('Network error. Check your connection and try again.');
      } else if (loadError instanceof ApiError && loadError.status >= 500) {
        setError(mode === 'login' ? 'Server error while signing in. Please try again shortly.' : 'Server error while creating your account. Please try again shortly.');
      } else {
        setError(mode === 'login' ? 'Unable to sign in right now.' : 'Unable to create your account right now.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout
      eyebrow="EasyEcom"
      title={content.heroTitle}
      description={content.heroDescription}
      points={content.points}
    >
      <AuthCard eyebrow={content.eyebrow} title={content.title} description={content.description}>
        <form className="auth-form" onSubmit={onSubmit}>
          {mode === 'signup' ? (
            <>
              <FormInput
                label="Full name"
                name="name"
                value={name}
                onChange={setName}
                autoComplete="name"
                disabled={submitting}
                required
                error={fieldErrors.name}
              />
              <FormInput
                label="Business name"
                name="business-name"
                value={businessName}
                onChange={setBusinessName}
                autoComplete="organization"
                disabled={submitting}
                required
                error={fieldErrors.businessName}
              />
            </>
          ) : null}

          <FormInput
            label="Email"
            name="email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="email"
            disabled={submitting}
            required
            error={fieldErrors.email}
          />
          <FormInput
            label="Password"
            name="password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            disabled={submitting}
            required
            error={fieldErrors.password}
          />

          {error ? <p className="auth-form-error" role="alert">{error}</p> : null}

          <div className="auth-form-actions">
            <PrimaryButton type="submit" disabled={submitting}>
              {submitting ? (mode === 'login' ? 'Signing In…' : 'Creating Account…') : mode === 'login' ? 'Sign In' : 'Create Account'}
            </PrimaryButton>
            {mode === 'login' ? (
              <div className="auth-inline-links">
                <a href="mailto:support@easy-ecom.online?subject=EasyEcom%20Password%20Reset">Forgot password?</a>
                <Link href="/signup">Create account</Link>
              </div>
            ) : (
              <div className="auth-inline-links">
                <span>Already have an account?</span>
                <Link href="/login">Login</Link>
              </div>
            )}
            <SecondaryButton href={mode === 'login' ? '/signup' : '/login'}>
              {mode === 'login' ? 'Create account' : 'Back to login'}
            </SecondaryButton>
          </div>
        </form>
      </AuthCard>
    </AuthLayout>
  );
}
