'use client';

import Link from 'next/link';
import { useEffect, useRef } from 'react';
import {
  BadgeDollarSign,
  BarChart3,
  Boxes,
  ClipboardList,
  Gauge,
  HandCoins,
  Menu,
  PackageSearch,
  RefreshCw,
  Settings,
  ShoppingCart,
  Sparkles,
  Users,
} from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';
import { getMobilePrimaryItems } from '@/lib/navigation';
import type { NavigationItem } from '@/types/navigation';

const ICONS = {
  dashboard: Gauge,
  reports: BarChart3,
  package: Boxes,
  catalog: Boxes,
  inventory: PackageSearch,
  sales: ShoppingCart,
  customers: Users,
  finance: HandCoins,
  returns: RefreshCw,
  admin: Sparkles,
  automation: ClipboardList,
  billing: BadgeDollarSign,
  settings: Settings,
} as const;

function getMobileNavigationIcon(icon: NavigationItem['icon']) {
  return ICONS[icon];
}

export function MobileBottomNav() {
  const pathname = usePathname();
  const { user } = useAuth();
  const primaryItems = getMobilePrimaryItems(user);
  const navRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const root = document.documentElement;
    const navElement = navRef.current;
    if (!navElement) {
      return;
    }

    const updateHeightVar = () => {
      root.style.setProperty('--mobile-bottom-nav-height', `${Math.ceil(navElement.offsetHeight)}px`);
    };

    updateHeightVar();
    window.addEventListener('resize', updateHeightVar);
    window.addEventListener('orientationchange', updateHeightVar);

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(updateHeightVar);
      observer.observe(navElement);
    }

    return () => {
      window.removeEventListener('resize', updateHeightVar);
      window.removeEventListener('orientationchange', updateHeightVar);
      observer?.disconnect();
    };
  }, []);

  const isCatalogRoute = pathname === '/catalog' || pathname.startsWith('/catalog/');

  return (
    <nav ref={navRef} className={isCatalogRoute ? 'mobile-bottom-nav is-catalog-context' : 'mobile-bottom-nav'} aria-label="Mobile navigation">
      {primaryItems.map((item) => {
        const Icon = getMobileNavigationIcon(item.icon);
        const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={isActive ? 'mobile-bottom-link active' : 'mobile-bottom-link'}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon size={18} aria-hidden="true" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
