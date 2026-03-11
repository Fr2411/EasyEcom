'use client';

import { usePathname } from 'next/navigation';
import { NAV_ITEMS } from '@/types/navigation';

const DEFAULT_TITLE = 'Operations Workspace';

export function TopHeader() {
  const pathname = usePathname();
  const matchedRoute = NAV_ITEMS.find((item) => item.href === pathname);

  return (
    <header className="top-header">
      <div>
        <p className="eyebrow">EasyEcom / {matchedRoute?.group ?? 'Overview'}</p>
        <p className="header-title">{matchedRoute?.label ?? DEFAULT_TITLE}</p>
        <p className="header-subtitle">Operations Workspace</p>
      </div>
      <div className="header-search" aria-label="Search placeholder">
        Search orders, SKUs, customers...
      </div>
      <div className="header-utilities">
        <button type="button" className="header-btn">+ New</button>
        <div className="header-pill">Live Workspace</div>
      </div>
    </header>
  );
}
