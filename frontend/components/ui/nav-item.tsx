'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart3,
  Bot,
  Boxes,
  ClipboardList,
  Gauge,
  HandCoins,
  Handshake,
  Home,
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
  home: Home,
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
  settings: Settings
} as const;

export function NavItem({
  item,
  collapsed = false,
}: {
  item: NavigationItem;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  const isActive = pathname === item.href;
  const Icon = ICONS[item.icon];

  return (
    <Link
      href={item.href}
      className={collapsed ? `${isActive ? 'nav-link active' : 'nav-link'} collapsed` : isActive ? 'nav-link active' : 'nav-link'}
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
    >
      <Icon size={16} aria-hidden="true" />
      <span className="nav-link-label">{item.label}</span>
    </Link>
  );
}
