'use client';

import { FormEvent, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useRouter } from 'next/navigation';
import { Command, Search, Sparkles } from 'lucide-react';
import { NAV_ITEMS } from '@/types/navigation';

const DEFAULT_TITLE = 'Operations Workspace';

type SearchScope = 'sales' | 'inventory' | 'returns';

const SEARCH_SCOPE_ROUTES: Record<SearchScope, string> = {
  sales: '/sales',
  inventory: '/inventory',
  returns: '/returns',
};

export function TopHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const matchedRoute = NAV_ITEMS.find((item) => item.href === pathname);
  const [scope, setScope] = useState<SearchScope>('sales');
  const [query, setQuery] = useState('');

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
          <p className="eyebrow">EasyEcom / {matchedRoute?.group ?? 'Overview'}</p>
          <span className="header-kicker-pill">
            <Sparkles size={14} aria-hidden="true" />
            Live workspace
          </span>
        </div>
        <p className="header-title">{matchedRoute?.label ?? DEFAULT_TITLE}</p>
        <p className="header-subtitle">Operations Workspace</p>
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
        <button type="button" className="header-btn">+ New</button>
      </div>
    </header>
  );
}
