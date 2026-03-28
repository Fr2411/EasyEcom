'use client';

import { FormEvent, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ArrowRight, Command, Search, Sparkles } from 'lucide-react';
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
        title: 'Home',
        subtitle: 'Daily control room',
        summary: 'Monitor the most important operational signals and jump into the right workspace faster.',
        searchScope: 'sales',
        actionLabel: 'Open dashboard',
        actionHref: '/dashboard',
      };
    case '/dashboard':
      return {
        section: 'Today',
        title: 'Dashboard',
        subtitle: 'Business pulse',
        summary: 'Review stock health, revenue signals, and the exceptions that need attention now.',
        searchScope: 'sales',
        actionLabel: 'Open reports',
        actionHref: '/reports',
      };
    case '/reports':
      return {
        section: 'Today',
        title: 'Reports',
        subtitle: 'Operational review',
        summary: 'Move from daily execution into trend review, finance visibility, and exception analysis.',
        searchScope: 'sales',
        actionLabel: 'Open finance',
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
      };
    case '/inventory':
      return {
        section: 'Commerce',
        title: 'Inventory',
        subtitle: 'Stock control',
        summary: 'Track on-hand stock, receive goods, and keep the ledger consistent across locations.',
        searchScope: 'inventory',
        actionLabel: 'Open purchases',
        actionHref: '/purchases',
      };
    case '/sales':
      return {
        section: 'Commerce',
        title: 'Sales',
        subtitle: 'Order desk',
        summary: 'Move quickly through order entry, fulfillment, and the exceptions that affect revenue.',
        searchScope: 'sales',
        actionLabel: 'Open customers',
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
        actionLabel: 'Open reports',
        actionHref: '/reports',
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
    case '/admin':
      return {
        section: 'System',
        title: 'Admin',
        subtitle: 'Tenant and platform',
        summary: 'Manage platform-level controls and tenant-wide configuration from one place.',
        searchScope: 'sales',
        actionLabel: 'Open settings',
        actionHref: '/settings',
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
    router.push(`${SEARCH_SCOPE_ROUTES[scope]}?${params.toString()}`);
  };

  return (
    <header className="top-header">
      <div className="header-copy">
        <div className="header-kicker-row">
          <p className="eyebrow">EasyEcom / {pageContext.section}</p>
          <span className="header-kicker-pill">
            <Sparkles size={14} aria-hidden="true" />
            Live workspace
          </span>
        </div>
        <p className="header-title">{pageContext.title ?? matchedRoute?.label ?? DEFAULT_TITLE}</p>
        <p className="header-subtitle">
          {pageContext.subtitle}. {pageContext.summary}
        </p>
      </div>
      <form className="header-search" aria-label="Global search" onSubmit={onSubmit}>
        <span className="header-search-icon" aria-hidden="true">
          <Search size={16} />
        </span>
        <select
          aria-label="Search scope"
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
          aria-label="Search query"
          className="header-search-input"
          placeholder="Search orders, SKUs, returns..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="header-search-button">Search</button>
      </form>
      <div className="header-utilities">
        <div className="header-command-chip">
          <Command size={14} aria-hidden="true" />
          Quick actions
        </div>
        <button
          type="button"
          className="header-btn"
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
