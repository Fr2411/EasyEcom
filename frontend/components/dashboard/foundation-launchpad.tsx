import Link from 'next/link';

const MODULES = [
  {
    href: '/catalog',
    title: 'Catalog',
    summary: 'Products, variants, categories, suppliers, and pricing guardrails start here.',
  },
  {
    href: '/inventory',
    title: 'Inventory',
    summary: 'Variant-level stock will be rebuilt from the immutable ledger and warehouse locations.',
  },
  {
    href: '/purchases',
    title: 'Purchases',
    summary: 'Inbound stock and supplier buying flows will use dedicated procurement records.',
  },
  {
    href: '/sales',
    title: 'Sales',
    summary: 'Orders, shipments, and payment states will return as explicit lifecycle commands.',
  },
  {
    href: '/customers',
    title: 'Customers',
    summary: 'Tenant-safe customer records will support CRM and sales linkage.',
  },
  {
    href: '/finance',
    title: 'Finance',
    summary: 'Operational finance will track payments, expenses, and return impact without full accounting complexity.',
  },
  {
    href: '/returns',
    title: 'Returns',
    summary: 'Returns and refunds will remain auditable and tied back to the original sale lines.',
  },
  {
    href: '/reports',
    title: 'Reports',
    summary: 'KPIs and reporting will be rebuilt on top of trusted transactional tables instead of brittle calculations.',
  },
  {
    href: '/admin',
    title: 'Admin',
    summary: 'Tenant onboarding, users, roles, and invitations will live here.',
  },
  {
    href: '/settings',
    title: 'Settings',
    summary: 'Client defaults, profile data, and session-safe operational settings will be managed here.',
  },
] as const;

type FoundationLaunchpadProps = {
  title: string;
  subtitle: string;
};

export function FoundationLaunchpad({ title, subtitle }: FoundationLaunchpadProps) {
  return (
    <section className="foundation-launchpad">
      <div className="foundation-hero">
        <p className="eyebrow">Rebuild Foundation</p>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
      <div className="foundation-grid">
        {MODULES.map((module) => (
          <Link key={module.href} href={module.href} className="foundation-card">
            <p className="foundation-card-kicker">Core Module</p>
            <h4>{module.title}</h4>
            <p>{module.summary}</p>
            <span>Open workspace</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
