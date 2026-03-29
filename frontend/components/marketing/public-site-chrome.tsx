'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';
import { ThemeToggle } from '@/components/theme/theme-toggle';

type PublicNavLink = {
  href: string;
  label: string;
};

const NAV_LINKS: PublicNavLink[] = [
  { href: '/#features', label: 'Features' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/login', label: 'Login' },
];

const FOOTER_GROUPS = [
  {
    title: 'Product',
    links: [
      { href: '/#features', label: 'Features' },
      { href: '/pricing', label: 'Pricing' },
    ],
  },
  {
    title: 'Company',
    links: [
      { href: '/about', label: 'About' },
      { href: '/contact', label: 'Contact' },
    ],
  },
  {
    title: 'Account',
    links: [
      { href: '/login', label: 'Login' },
      { href: '/login?mode=signup', label: 'Sign Up' },
    ],
  },
  {
    title: 'Legal',
    links: [
      { href: '/terms', label: 'Terms' },
      { href: '/privacy', label: 'Privacy' },
    ],
  },
];

export function PublicSiteChrome({
  children,
  ctaHref = '/login?mode=signup',
  ctaLabel = 'Start Free',
}: {
  children: ReactNode;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <AuthRouteGuard mode="public-only">
      <main className="marketing-page">
        <header className="marketing-shell">
          <nav className="marketing-nav">
            <Link href="/" className="marketing-brand" aria-label="EasyEcom home">
              <EasyEcomLogo className="easyecom-logo" imageClassName="easyecom-logo-image" />
              <div>
                <strong>EasyEcom</strong>
                <span>AI sales and operations system</span>
              </div>
            </Link>

            <div className="marketing-nav-actions">
              <div className="marketing-theme-wrap">
                <ThemeToggle />
              </div>
              <div className="marketing-nav-links">
                {NAV_LINKS.map((link) => (
                  <Link key={link.href} href={link.href} className="marketing-nav-link">
                    {link.label}
                  </Link>
                ))}
                <Link href={ctaHref} className="button-link btn-primary">
                  {ctaLabel}
                </Link>
              </div>
            </div>
          </nav>
        </header>

        {children}

        <footer className="marketing-footer-shell">
          <div className="marketing-footer">
            <div className="marketing-footer-brand">
              <Link href="/" className="marketing-brand" aria-label="EasyEcom home">
                <EasyEcomLogo className="easyecom-logo" imageClassName="easyecom-logo-image" />
                <div>
                  <strong>EasyEcom</strong>
                  <span>AI sales and operations system</span>
                </div>
              </Link>
            </div>
            <div className="marketing-footer-grid">
              {FOOTER_GROUPS.map((group) => (
                <section key={group.title} className="marketing-footer-group" aria-label={group.title}>
                  <h2>{group.title}</h2>
                  <ul>
                    {group.links.map((link) => (
                      <li key={link.href}>
                        <Link href={link.href}>{link.label}</Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </div>
        </footer>
      </main>
    </AuthRouteGuard>
  );
}
