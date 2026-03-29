import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, test, vi } from 'vitest';
import PublicLandingPage from '@/app/page';

vi.mock('@/components/auth/auth-route-guard', () => ({
  AuthRouteGuard: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('@/components/theme/theme-toggle', () => ({
  ThemeToggle: () => <div>Theme toggle</div>,
}));

vi.mock('@/components/branding/easy-ecom-logo', () => ({
  EasyEcomLogo: () => <div>EasyEcom Logo</div>,
}));

afterEach(() => {
  cleanup();
});

describe('PublicLandingPage', () => {
  test('renders the required hero copy and CTA links', () => {
    render(<PublicLandingPage />);

    expect(screen.getByRole('heading', { name: 'Turn customer chats into sales — automatically' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Start Free — No Credit Card' }).getAttribute('href')).toBe('/login?mode=signup');
    expect(screen.getByRole('link', { name: 'See How It Works' }).getAttribute('href')).toBe('/#how-it-works');
    expect(screen.getByText('Used by growing businesses to handle sales, inventory, and operations in one place.')).toBeTruthy();
  });

  test('renders the navbar, pricing preview, and footer routes', () => {
    render(<PublicLandingPage />);

    expect(screen.getAllByRole('link', { name: 'Features' }).some((link) => link.getAttribute('href') === '/#features')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'Pricing' }).some((link) => link.getAttribute('href') === '/pricing')).toBe(true);
    expect(screen.getAllByRole('link', { name: 'Login' }).some((link) => link.getAttribute('href') === '/login')).toBe(true);
    expect(screen.getByRole('link', { name: 'View Full Pricing' }).getAttribute('href')).toBe('/pricing');
    expect(screen.getByRole('link', { name: 'About' }).getAttribute('href')).toBe('/about');
    expect(screen.getByRole('link', { name: 'Contact' }).getAttribute('href')).toBe('/contact');
    expect(screen.getByRole('link', { name: 'Terms' }).getAttribute('href')).toBe('/terms');
    expect(screen.getByRole('link', { name: 'Privacy' }).getAttribute('href')).toBe('/privacy');
  });
});
