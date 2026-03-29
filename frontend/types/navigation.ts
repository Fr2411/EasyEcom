export type NavigationGroup = 'Today' | 'Commerce' | 'Channels' | 'Operations' | 'System';

export type NavigationItem = {
  href: string;
  label: string;
  group: NavigationGroup;
  icon:
    | 'home'
    | 'dashboard'
    | 'reports'
    | 'package'
    | 'catalog'
    | 'inventory'
    | 'sales'
    | 'customers'
    | 'purchases'
  | 'finance'
  | 'returns'
  | 'billing'
  | 'admin'
  | 'integrations'
  | 'ai'
    | 'automation'
    | 'settings';
};

export const NAV_GROUP_ORDER: NavigationGroup[] = [
  'Today',
  'Commerce',
  'Channels',
  'Operations',
  'System',
];

export const NAV_ITEMS: NavigationItem[] = [
  { href: '/', label: 'Home', group: 'Today', icon: 'home' },
  { href: '/dashboard', label: 'Dashboard', group: 'Today', icon: 'dashboard' },
  { href: '/reports', label: 'Reports', group: 'Today', icon: 'reports' },
  { href: '/catalog', label: 'Catalog', group: 'Commerce', icon: 'catalog' },
  { href: '/inventory', label: 'Inventory', group: 'Commerce', icon: 'inventory' },
  { href: '/sales', label: 'Sales', group: 'Commerce', icon: 'sales' },
  { href: '/customers', label: 'Customers', group: 'Commerce', icon: 'customers' },
  { href: '/purchases', label: 'Purchases', group: 'Commerce', icon: 'purchases' },
  { href: '/sales-agent', label: 'Sales Agent', group: 'Commerce', icon: 'ai' },
  { href: '/ai-review', label: 'AI Review', group: 'Commerce', icon: 'ai' },
  { href: '/integrations', label: 'Integrations', group: 'Channels', icon: 'integrations' },
  { href: '/automation', label: 'Automation', group: 'System', icon: 'automation' },
  { href: '/finance', label: 'Finance', group: 'Operations', icon: 'finance' },
  { href: '/returns', label: 'Returns', group: 'Operations', icon: 'returns' },
  { href: '/billing', label: 'Billing', group: 'System', icon: 'billing' },
  { href: '/admin', label: 'Admin', group: 'System', icon: 'admin' },
  { href: '/settings', label: 'Settings', group: 'System', icon: 'settings' }
];
