'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Bot,
  Boxes,
  ClipboardList,
  BadgeDollarSign,
  Gauge,
  HandCoins,
  Handshake,
  PackageSearch,
  Receipt,
  RefreshCw,
  Settings,
  ShoppingCart,
  Sparkles,
  Users
} from 'lucide-react';
import { NavigationItem } from '@/types/navigation';

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
  integrations: Handshake,
  ai: Bot,
  automation: ClipboardList,
  purchases: Receipt,
  billing: BadgeDollarSign,
  settings: Settings
} as const;

export function getNavigationIcon(icon: NavigationItem['icon']) {
  return ICONS[icon];
}

export function NavItem({
  item,
  collapsed = false,
  onSelect,
}: {
  item: NavigationItem;
  collapsed?: boolean;
  onSelect?: () => void;
}) {
  const pathname = usePathname();
  const isActive = item.href === '/' ? pathname === item.href : pathname === item.href || pathname.startsWith(`${item.href}/`);
  const Icon = getNavigationIcon(item.icon);

  return (
    <Link
      href={item.href}
      aria-current={isActive ? 'page' : undefined}
      className={collapsed ? `${isActive ? 'nav-link active' : 'nav-link'} collapsed` : isActive ? 'nav-link active' : 'nav-link'}
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
      onClick={onSelect}
    >
      <Icon size={16} aria-hidden="true" />
      <span className="nav-link-label">{item.label}</span>
    </Link>
  );
}
