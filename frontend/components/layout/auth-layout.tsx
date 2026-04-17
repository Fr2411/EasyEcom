import Link from 'next/link';
import type { ReactNode } from 'react';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';

export function AuthLayout({
  eyebrow,
  title,
  description,
  points,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  points: string[];
  children: ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="auth-hero">
        <div className="auth-hero-logo">
          <Link href="/" className="marketing-brand auth-hero-brand" aria-label="EasyEcom home">
            <EasyEcomLogo className="easyecom-logo easyecom-logo-hero" imageClassName="easyecom-logo-image easyecom-logo-hero" />
            <div>
              <strong>EasyEcom</strong>
              <span>Commerce operating system</span>
            </div>
          </Link>
        </div>
        <p className="auth-hero-eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="auth-hero-copy">{description}</p>
        <ul className="auth-hero-points">
          {points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </section>
      {children}
    </main>
  );
}
