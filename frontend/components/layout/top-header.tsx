'use client';

import { FormEvent, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowRight, Search } from 'lucide-react';
import { NAV_ITEMS } from '@/types/navigation';

const DEFAULT_TITLE = 'Operations Workspace';

type SearchScope = 'sales' | 'inventory' | 'returns';

type HeaderContext = {
  section: string;
  title: string;
  subtitle: string;
  summary: string;
  searchScope: SearchScope;
  actionLabel: string;
  actionHref: string;
  actionTone?: 'primary' | 'secondary' | 'quiet';
};

const SEARCH_SCOPE_ROUTES: Record<SearchScope, string> = {
  sales: '/sales',
  inventory: '/inventory',
  returns: '/returns',
};

function getHeaderContext(pathname: string): HeaderContext {
  switch (pathname) {
    case '/':
      return {
        section: 'Today',
        title: 'Dashboard',
        subtitle: 'Business pulse',
        summary: 'Review stock health, revenue signals, and the exceptions that need attention now.',
        searchScope: 'sales',
        actionLabel: 'Reports',
        actionHref: '/reports',
        actionTone: 'quiet',
      };
    case '/dashboard':
      return {
        section: 'Today',
        title: 'Dashboard',
        subtitle: 'Business pulse',
        summary: 'Review stock health, revenue signals, and the exceptions that need attention now.',
        searchScope: 'sales',
        actionLabel: 'Reports',
        actionHref: '/reports',
        actionTone: 'quiet',
      };
    case '/reports':
      return {
        section: 'Today',
        title: 'Reports',
        subtitle: 'Operational review',
        summary: 'Move from daily execution into trend review, finance visibility, and exception analysis.',
        searchScope: 'sales',
        actionLabel: 'Open Finance workspace',
        actionHref: '/finance',
      };
    case '/catalog':
      return {
        section: 'Commerce',
        title: 'Catalog',
        subtitle: 'Product master',
        summary: 'Manage product records and keep saleable inventory aligned with variant truth.',
        searchScope: 'inventory',
        actionLabel: 'Open inventory',
        actionHref: '/inventory',
        actionTone: 'quiet',
      };
    case '/inventory':
      return {
        section: '',
        title: 'Inventory',
        subtitle: '',
        summary: '',
        searchScope: 'inventory',
        actionLabel: 'Open catalog',
        actionHref: '/catalog',
      };
    case '/sales':
      return {
        section: 'Commerce',
        title: 'Sales',
        subtitle: 'Order desk',
        summary: 'Move quickly through order entry, fulfillment, and the exceptions that affect revenue.',
        searchScope: 'sales',
        actionLabel: 'Open Customers workspace',
        actionHref: '/customers',
      };
    case '/customers':
      return {
        section: 'Commerce',
        title: 'Customers',
        subtitle: 'Account history',
        summary: 'Review customer activity and connect service decisions to real order history.',
        searchScope: 'sales',
        actionLabel: 'Open sales',
        actionHref: '/sales',
      };
    case '/automation':
      return {
        section: 'Operations',
        title: 'Automation',
        subtitle: 'Rules and jobs',
        summary: 'Control business automation from a single tenant-safe operational layer.',
        searchScope: 'inventory',
        actionLabel: 'Open reports',
        actionHref: '/reports',
      };
    case '/finance':
      return {
        section: 'Operations',
        title: 'Finance',
        subtitle: 'Cash and reconciliation',
        summary: 'Monitor money movement, reconciliation, and financial visibility from the same workspace.',
        searchScope: 'sales',
        actionLabel: 'Open Billing workspace',
        actionHref: '/billing',
      };
    case '/returns':
      return {
        section: 'Operations',
        title: 'Returns',
        subtitle: 'Reverse logistics',
        summary: 'Handle returns, restocks, and recovery workflows without losing stock accuracy.',
        searchScope: 'returns',
        actionLabel: 'Open inventory',
        actionHref: '/inventory',
      };
    case '/billing':
      return {
        section: 'Operations',
        title: 'Billing',
        subtitle: 'Subscription state',
        summary: 'Trust backend subscription state and manage checkout, portal, and cancellation from one owner-only workspace.',
        searchScope: 'sales',
        actionLabel: 'View pricing',
        actionHref: '/pricing',
      };
    case '/billing/success':
      return {
        section: 'Operations',
        title: 'Billing success',
        subtitle: 'Billing return',
        summary: 'Review the live backend subscription state after the hosted billing flow returns you to the app.',
        searchScope: 'sales',
        actionLabel: 'Open billing',
        actionHref: '/billing',
      };
    case '/billing/cancel':
      return {
        section: 'Operations',
        title: 'Billing cancelled',
        subtitle: 'Billing return',
        summary: 'The app uses backend subscription state, so cancelled hosted flows still show the actual account state.',
        searchScope: 'sales',
        actionLabel: 'Open billing',
        actionHref: '/billing',
      };
    case '/admin':
      return {
        section: 'System',
        title: 'Admin',
        subtitle: 'Tenant and platform',
        summary: 'Find an existing tenant or stage a new onboarding draft from one intent bar.',
        searchScope: 'sales',
        actionLabel: 'Start onboarding',
        actionHref: '/admin?mode=create',
      };
    case '/settings':
      return {
        section: 'System',
        title: 'Settings',
        subtitle: 'Workspace config',
        summary: 'Tune business defaults, access, and workspace behavior with fewer hidden steps.',
        searchScope: 'sales',
        actionLabel: 'Open admin',
        actionHref: '/admin',
      };
    default:
      return {
        section: 'Overview',
        title: DEFAULT_TITLE,
        subtitle: 'Operations Workspace',
        summary: 'Use the shell to move between the core business workspaces.',
        searchScope: 'sales',
        actionLabel: 'Open dashboard',
        actionHref: '/dashboard',
      };
  }
}

export function TopHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const matchedRoute = NAV_ITEMS.find((item) => item.href === pathname);
  const pageContext = getHeaderContext(pathname);
  const [scope, setScope] = useState<SearchScope>(pageContext.searchScope);
  const [query, setQuery] = useState('');

  useEffect(() => {
    setScope(pageContext.searchScope);
  }, [pageContext.searchScope]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    const params = new URLSearchParams({ q: trimmed });
    const targetRoute = SEARCH_SCOPE_ROUTES[scope];
    router.push(`${targetRoute}?${params.toString()}`);
  };
  const actionToneClass =
    pageContext.actionTone === 'primary'
      ? ''
      : pageContext.actionTone === 'quiet'
        ? 'header-btn-secondary header-btn-quiet'
        : 'header-btn-secondary';
  const actionClassName = `header-btn ${actionToneClass} header-cross-module-action`.trim();

  return (
    <header className="top-header top-header-consistent">
      <div className="header-copy">
        <p className="header-title">{pageContext.title ?? matchedRoute?.label ?? DEFAULT_TITLE}</p>
      </div>
      <form className="header-search" aria-label="Global workspace search" onSubmit={onSubmit}>
        <span className="header-search-icon" aria-hidden="true">
          <Search size={16} />
        </span>
        <select
          aria-label="Global search scope"
          className="header-search-scope"
          value={scope}
          onChange={(event) => setScope(event.target.value as SearchScope)}
        >
          <option value="sales">Orders</option>
          <option value="inventory">SKUs</option>
          <option value="returns">Returns</option>
        </select>
        <input
          type="search"
          aria-label="Global search query"
          className="header-search-input"
          placeholder="Search orders, SKUs, and returns"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="header-search-button">Search</button>
      </form>
      <div className="header-utilities">
        <button
          type="button"
          className={actionClassName}
          onClick={() => router.push(pageContext.actionHref)}
          aria-label={pageContext.actionLabel}
        >
          {pageContext.actionLabel}
          <ArrowRight size={14} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
