import Link from 'next/link';
import type { ReactNode } from 'react';

type LegalLink = {
  href: string;
  label: string;
};

type LegalPageShellProps = {
  eyebrow?: string;
  title: string;
  lead: string;
  effectiveDate: string;
  contactEmail: string;
  links?: LegalLink[];
  children: ReactNode;
};

export function LegalPageShell({
  eyebrow = 'EasyEcom Legal',
  title,
  lead,
  effectiveDate,
  contactEmail,
  links = [],
  children,
}: LegalPageShellProps) {
  return (
    <main className="legal-page">
      <section className="legal-hero">
        <p className="legal-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="legal-lead">{lead}</p>
        <div className="legal-meta">
          <span>Effective date: {effectiveDate}</span>
          <span>Contact: {contactEmail}</span>
        </div>
        {links.length ? (
          <nav className="legal-links" aria-label="Legal pages">
            {links.map((link) => (
              <Link key={link.href} href={link.href} className="legal-link-chip">
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}
      </section>

      <section className="legal-card">{children}</section>
    </main>
  );
}
