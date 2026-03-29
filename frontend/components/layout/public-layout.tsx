import type { ReactNode } from 'react';
import { PublicFooter } from '@/components/marketing/public-footer';
import { PublicNavbar } from '@/components/marketing/public-navbar';

export function PublicLayout({
  children,
  ctaHref = '/signup',
  ctaLabel = 'Start Free',
}: {
  children: ReactNode;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <main className="marketing-page">
      <PublicNavbar ctaHref={ctaHref} ctaLabel={ctaLabel} />
      {children}
      <PublicFooter />
    </main>
  );
}
