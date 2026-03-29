'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle2, MoonStar, SunMedium, Zap } from 'lucide-react';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';
import { ThemeToggle } from '@/components/theme/theme-toggle';

const proofPoints = [
  'Variant-true inventory and selling flows',
  'Finance, returns, AI review, and billing in one product',
  'Built for importers, distributors, and retail operators',
];

const platformSections = [
  {
    eyebrow: 'Operational command',
    title: 'Run catalog, stock, sales, and returns from one deliberate workspace.',
    body: 'EasyEcom is designed so operators do not have to stitch spreadsheets, chat apps, and disconnected dashboards together just to keep the business moving.',
    icon: Zap,
  },
  {
    eyebrow: 'Revenue layer',
    title: 'Turn day-to-day commerce data into pricing, follow-up, and sales-agent leverage.',
    body: 'The product keeps tenant data clean and structured so AI review, automation, and guided workflows can actually make better recommendations.',
    icon: CheckCircle2,
  },
];

const featureColumns = [
  {
    title: 'For the owner',
    items: ['Billing-aware SaaS controls', 'Finance visibility and receivables', 'Plan upgrades through Stripe Checkout', 'Team-safe access by role'],
  },
  {
    title: 'For the operator',
    items: ['Guided inventory intake', 'Intent-first sales flow', 'Return and refund tracking', 'Reliable variant-level stock'],
  },
  {
    title: 'For scale',
    items: ['Integrations and diagnostics', 'AI review queue', 'Automation foundation', 'Tenant-safe multi-client architecture'],
  },
];

export default function PublicLandingPage() {
  return (
    <AuthRouteGuard mode="public-only">
      <main className="marketing-page">
        <section className="marketing-hero">
          <header className="marketing-nav">
            <Link href="/" className="marketing-brand" aria-label="EasyEcom home">
              <EasyEcomLogo className="easyecom-logo" imageClassName="easyecom-logo-image" />
              <div>
                <strong>EasyEcom</strong>
                <span>Commerce operating system</span>
              </div>
            </Link>

            <div className="marketing-nav-actions">
              <ThemeToggle />
              <Link href="/pricing" className="button-link secondary">
                Pricing
              </Link>
              <Link href="/login" className="button-link btn-primary">
                Sign in
              </Link>
            </div>
          </header>

          <div className="marketing-hero-grid">
            <div className="marketing-copy">
              <p className="marketing-kicker">Modern SaaS UX, adapted for commerce operations</p>
              <h1>Make the interface lead the work before the user has to think.</h1>
              <p className="marketing-lead">
                Inspired by high-clarity SaaS landing pages, this public surface introduces EasyEcom as a guided commerce system for businesses that buy, stock, sell, return, and grow through cleaner operational data.
              </p>

              <div className="marketing-cta-row">
                <Link href="/login?mode=signup" className="button-link btn-primary">
                  Open your workspace
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <Link href="/pricing" className="button-link secondary">
                  Compare plans
                </Link>
              </div>

              <div className="marketing-proof-row" aria-label="Platform highlights">
                {proofPoints.map((point) => (
                  <span key={point}>
                    <CheckCircle2 size={15} aria-hidden="true" />
                    {point}
                  </span>
                ))}
              </div>
            </div>

            <aside className="marketing-showcase">
              <div className="marketing-showcase-card emphasis">
                <div className="marketing-showcase-head">
                  <span>Live workflow</span>
                  <strong>Intent-first workspace</strong>
                </div>
                <p>
                  Search, create, and follow-up decisions do not begin with blank forms. The UI stages likely actions, reveals relevant state, and holds the final write until the operator confirms.
                </p>
                <div className="marketing-pill-row">
                  <span>
                    <SunMedium size={14} aria-hidden="true" />
                    Light mode
                  </span>
                  <span>
                    <MoonStar size={14} aria-hidden="true" />
                    Dark mode
                  </span>
                  <span>System default</span>
                </div>
              </div>
              <div className="marketing-showcase-grid">
                <article className="marketing-showcase-card">
                  <p className="eyebrow">Sales</p>
                  <strong>Customer and product clues become draft orders.</strong>
                  <span>The interface suggests next line items and keeps fulfillment explicit.</span>
                </article>
                <article className="marketing-showcase-card">
                  <p className="eyebrow">Finance</p>
                  <strong>Commerce events post into finance without separate shadow work.</strong>
                  <span>Sales, returns, and manual operating transactions stay visible and auditable.</span>
                </article>
              </div>
            </aside>
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-section-heading">
            <p className="marketing-kicker">Built for real teams</p>
            <h2>Structured like a product, not a pile of dashboards.</h2>
          </div>
          <div className="marketing-columns">
            {platformSections.map((section) => {
              const Icon = section.icon;
              return (
                <article key={section.title} className="marketing-column-card">
                  <div className="marketing-column-icon">
                    <Icon size={18} aria-hidden="true" />
                  </div>
                  <p className="eyebrow">{section.eyebrow}</p>
                  <h3>{section.title}</h3>
                  <p>{section.body}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section className="marketing-section marketing-section-alt">
          <div className="marketing-section-heading">
            <p className="marketing-kicker">Why it feels different</p>
            <h2>Operators should feel guided, not burdened.</h2>
          </div>
          <div className="marketing-feature-grid">
            {featureColumns.map((column) => (
              <article key={column.title} className="marketing-feature-card">
                <h3>{column.title}</h3>
                <ul>
                  {column.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="marketing-section">
          <div className="marketing-cta-banner">
            <div>
              <p className="marketing-kicker">Start clean</p>
              <h2>Begin on Free, upgrade through Stripe when the paid modules matter.</h2>
              <p>
                Light product surface, heavier operational capability. That is the balance EasyEcom should keep.
              </p>
            </div>
            <div className="marketing-cta-row">
              <Link href="/login?mode=signup" className="button-link btn-primary">
                Create account
              </Link>
              <Link href="/pricing" className="button-link secondary">
                View plans
              </Link>
            </div>
          </div>
        </section>
      </main>
    </AuthRouteGuard>
  );
}
