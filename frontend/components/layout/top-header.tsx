'use client';

import { FormEvent, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Search } from 'lucide-react';
import { NAV_ITEMS } from '@/types/navigation';

const DEFAULT_TITLE = 'Operations Workspace';

type HeaderSearchConfig = {
  targetRoute: string;
  placeholder: string;
  ariaLabel: string;
};

type HeaderContext = {
  title: string;
  search: HeaderSearchConfig | null;
};

function getHeaderContext(pathname: string): HeaderContext {
  if (pathname === '/' || pathname === '/dashboard') {
    return {
      title: 'Dashboard',
      search: null,
    };
  }

  if (pathname === '/reports') {
    return {
      title: 'Reports',
      search: null,
    };
  }

  if (pathname === '/catalog') {
    return {
      title: 'Catalog',
      search: null,
    };
  }

  if (pathname === '/inventory' || pathname === '/products-stock' || pathname === '/inventory/products') {
    return {
      title: 'Inventory',
      search: null,
    };
  }

  if (pathname.startsWith('/sales')) {
    return {
      title: 'Sales',
      search: {
        targetRoute: '/sales',
        placeholder: 'Search order number, customer phone, or email',
        ariaLabel: 'Sales search',
      },
    };
  }

  if (pathname === '/customers') {
    return {
      title: 'Customers',
      search: {
        targetRoute: '/customers',
        placeholder: 'Search customer name, phone, or email',
        ariaLabel: 'Customer search',
      },
    };
  }

  if (pathname === '/automation') {
    return {
      title: 'Automation',
      search: null,
    };
  }

  if (pathname === '/finance') {
    return {
      title: 'Finance',
      search: null,
    };
  }

  if (pathname === '/returns') {
    return {
      title: 'Returns',
      search: {
        targetRoute: '/returns',
        placeholder: 'Search return number, order number, phone, or email',
        ariaLabel: 'Returns search',
      },
    };
  }

  if (pathname.startsWith('/billing')) {
    return {
      title: 'Billing',
      search: null,
    };
  }

  if (pathname === '/admin') {
    return {
      title: 'Admin',
      search: null,
    };
  }

  if (pathname === '/settings') {
    return {
      title: 'Settings',
      search: null,
    };
  }

  return {
    title: NAV_ITEMS.find((item) => item.href === pathname)?.label ?? DEFAULT_TITLE,
    search: null,
  };
}

export function TopHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const matchedRoute = NAV_ITEMS.find((item) => item.href === pathname);
  const pageContext = getHeaderContext(pathname);
  const [query, setQuery] = useState('');

  useEffect(() => {
    setQuery('');
  }, [pathname]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || !pageContext.search) return;

    const params = new URLSearchParams({ q: trimmed });
    router.push(`${pageContext.search.targetRoute}?${params.toString()}`);
  };

  return (
    <header
      className={pageContext.search ? 'top-header top-header-consistent has-context-search' : 'top-header top-header-consistent no-context-search'}
    >
      <div className="header-copy">
        <p className="header-title">{pageContext.title ?? matchedRoute?.label ?? DEFAULT_TITLE}</p>
      </div>
      {pageContext.search ? (
        <form className="header-search" aria-label={pageContext.search.ariaLabel} onSubmit={onSubmit}>
          <span className="header-search-icon" aria-hidden="true">
            <Search size={16} />
          </span>
          <input
            type="search"
            aria-label={pageContext.search.ariaLabel}
            className="header-search-input"
            placeholder={pageContext.search.placeholder}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="submit" className="header-search-button">Search</button>
        </form>
      ) : null}
    </header>
  );
}
