'use client';

import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { useState } from 'react';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';
import { ThemeToggle } from '@/components/theme/theme-toggle';

const NAV_LINKS = [
  { href: '/#features', label: 'Features' },
  { href: '/pricing', label: 'Pricing' },
  { href: '/login', label: 'Login' },
];

export function PublicNavbar({ ctaHref = '/signup', ctaLabel = 'Start Free' }: { ctaHref?: string; ctaLabel?: string }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="marketing-shell">
      <nav className="marketing-nav" aria-label="Public navigation">
        <Link href="/" className="marketing-brand" aria-label="EasyEcom home">
          <EasyEcomLogo className="easyecom-logo" imageClassName="easyecom-logo-image" />
          <div>
            <strong>EasyEcom</strong>
            <span>Business operating system</span>
          </div>
        </Link>

        <button
          type="button"
          className="marketing-mobile-toggle"
          onClick={() => setMobileOpen((current) => !current)}
          aria-expanded={mobileOpen}
          aria-controls="public-nav-links"
          aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
        >
          {mobileOpen ? <X size={18} aria-hidden="true" /> : <Menu size={18} aria-hidden="true" />}
        </button>

        <div className="marketing-nav-actions">
          <div className="marketing-theme-wrap">
            <ThemeToggle />
          </div>
          <div
            id="public-nav-links"
            className={mobileOpen ? 'marketing-nav-links mobile-open' : 'marketing-nav-links'}
          >
            {NAV_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="marketing-nav-link" onClick={() => setMobileOpen(false)}>
                {link.label}
              </Link>
            ))}
            <Link href={ctaHref} className="button-link btn-primary" onClick={() => setMobileOpen(false)}>
              {ctaLabel}
            </Link>
          </div>
        </div>
      </nav>
    </header>
  );
}
