import Link from 'next/link';
import { HoverHint } from '@/components/ui/hover-hint';

const MODULES = [
  {
    href: '/inventory',
    title: 'Inventory',
    summary: 'Receive-first product intake, available stock, adjustments, and low-stock workflows now share one inventory command center.',
  },
  {
    href: '/sales',
    title: 'Sales',
    summary: 'Order lifecycle, hidden customer lookup by phone or email, and full stock reservation rules live here.',
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
        <h3 className="workspace-heading">
          {title}
          <HoverHint text={subtitle} label={`${title} help`} />
        </h3>
      </div>
      <div className="foundation-grid">
        {MODULES.map((module) => (
          <Link key={module.href} href={module.href} className="foundation-card">
            <p className="foundation-card-kicker">Core Module</p>
            <h4 className="workspace-heading">
              {module.title}
              <HoverHint text={module.summary} label={`${module.title} help`} />
            </h4>
            <span>Open workspace</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
