'use client';

import { FormEvent, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowRight, Search } from 'lucide-react';
import { NAV_ITEMS } from '@/types/navigation';
import { ThemeToggle } from '@/components/theme/theme-toggle';

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
        actionLabel: 'View purchases',
        actionHref: '/purchases',
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
    case '/purchases':
      return {
        section: 'Commerce',
        title: 'Purchases',
        subtitle: 'Inbound stock',
        summary: 'Keep receiving, vendor tracking, and stock intake aligned with inventory truth.',
        searchScope: 'inventory',
        actionLabel: 'Open inventory',
        actionHref: '/inventory',
      };
    case '/sales-agent':
      return {
        section: 'Channels',
        title: 'Sales Agent',
        subtitle: 'Conversation desk',
        summary: 'Support customer conversations with tenant-safe product and stock context.',
        searchScope: 'sales',
        actionLabel: 'Open AI review',
        actionHref: '/ai-review',
      };
    case '/ai-review':
      return {
        section: 'Channels',
        title: 'AI Review',
        subtitle: 'Approval queue',
        summary: 'Review and control outbound AI actions before they reach customers.',
        searchScope: 'sales',
        actionLabel: 'Open sales agent',
        actionHref: '/sales-agent',
      };
    case '/integrations':
      return {
        section: 'Channels',
        title: 'Integrations',
        subtitle: 'Channel health',
        summary: 'Keep channels and external connections visible from one operational page.',
        searchScope: 'sales',
        actionLabel: 'Open automation',
        actionHref: '/automation',
      };
    case '/automation':
      return {
        section: 'Operations',
        title: 'Automation',
        subtitle: 'Rules and jobs',
        summary: 'Control business automation from a single tenant-safe operational layer.',
        searchScope: 'inventory',
        actionLabel: 'Open integrations',
        actionHref: '/integrations',
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
  const isCatalogRoute = pathname === '/catalog';
  const isSalesRoute = pathname === '/sales';
  const headerClassName = [
    'top-header',
    isCatalogRoute ? 'top-header-catalog' : '',
    isSalesRoute ? 'top-header-sales' : '',
  ]
    .filter(Boolean)
    .join(' ');
  const focusCatalogFinder = () => {
    if (typeof window === 'undefined') return;
    window.requestAnimationFrame(() => {
      const finder = document.getElementById('catalog-local-finder-input');
      if (finder instanceof HTMLInputElement) {
        finder.focus();
        finder.select();
      }
    });
  };

  useEffect(() => {
    setScope(pageContext.searchScope);
  }, [pageContext.searchScope]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    const params = new URLSearchParams({ q: trimmed });
    const targetRoute = isCatalogRoute ? '/catalog' : SEARCH_SCOPE_ROUTES[scope];
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
    <header className={headerClassName}>
      {isCatalogRoute ? (
        <a className="header-catalog-skip-link" href="#catalog-local-finder-input" onClick={focusCatalogFinder}>
          Skip to Catalog finder
        </a>
      ) : null}
      <div className="header-copy">
        <p className="header-title">{pageContext.title ?? matchedRoute?.label ?? DEFAULT_TITLE}</p>
        {pageContext.subtitle ? <p className="header-subtitle">{pageContext.subtitle}</p> : null}
        {pageContext.summary ? <p className="header-summary">{pageContext.summary}</p> : null}
      </div>
      <form
        className={isCatalogRoute ? 'header-search header-search-secondary' : 'header-search'}
        aria-label={isCatalogRoute ? 'Secondary global workspace search' : 'Global workspace search'}
        onSubmit={onSubmit}
      >
        {isCatalogRoute ? (
          <span className="header-search-context">Catalog finder is primary on this page. Use this only for cross-module navigation.</span>
        ) : null}
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
          placeholder={isCatalogRoute ? 'Secondary global search: orders, SKUs, returns' : 'Global search: orders, SKUs, returns'}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="header-search-button">{isCatalogRoute ? 'Global search' : 'Search all'}</button>
      </form>
      <div className={isCatalogRoute ? 'header-utilities header-utilities-catalog' : 'header-utilities'}>
        <div className={isCatalogRoute ? 'header-theme-cluster' : undefined}>
          <div className={isCatalogRoute ? 'header-theme-mobile header-theme-catalog' : 'header-theme-mobile'} aria-label="Display mode">
            <ThemeToggle variant={isCatalogRoute ? 'header-catalog' : 'default'} />
          </div>
        </div>
        <div className={isCatalogRoute ? 'header-action-cluster' : undefined}>
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
      </div>
    </header>
  );
}
