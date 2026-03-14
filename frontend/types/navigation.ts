export type NavigationItem = {
  href: string;
  label: string;
  group: 'Overview' | 'Commerce' | 'Operations' | 'System';
  icon:
    | 'home'
    | 'dashboard'
    | 'reports'
    | 'package'
    | 'catalog'
    | 'inventory'
    | 'sales'
    | 'customers'
    | 'finance'
    | 'returns'
    | 'admin'
    | 'integrations'
    | 'ai'
    | 'automation'
    | 'purchases'
    | 'settings';
};

export const NAV_ITEMS: NavigationItem[] = [
  { href: '/', label: 'Home', group: 'Overview', icon: 'home' },
  { href: '/dashboard', label: 'Dashboard', group: 'Overview', icon: 'dashboard' },
  { href: '/reports', label: 'Reports', group: 'Overview', icon: 'reports' },
  { href: '/catalog', label: 'Catalog', group: 'Commerce', icon: 'catalog' },
  { href: '/inventory', label: 'Inventory', group: 'Commerce', icon: 'inventory' },
  { href: '/purchases', label: 'Purchases', group: 'Commerce', icon: 'purchases' },
  { href: '/sales', label: 'Sales', group: 'Commerce', icon: 'sales' },
  { href: '/customers', label: 'Customers', group: 'Commerce', icon: 'customers' },
  { href: '/finance', label: 'Finance', group: 'Operations', icon: 'finance' },
  { href: '/returns', label: 'Returns', group: 'Operations', icon: 'returns' },
  { href: '/admin', label: 'Admin', group: 'System', icon: 'admin' },
  { href: '/settings', label: 'Settings', group: 'System', icon: 'settings' }
];
