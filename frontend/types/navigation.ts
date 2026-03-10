export type NavigationItem = {
  href: string;
  label: string;
};

export const NAV_ITEMS: NavigationItem[] = [
  { href: '/', label: 'Home' },
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/products-stock', label: 'Products & Stock' },
  { href: '/inventory', label: 'Inventory' },
  { href: '/sales', label: 'Sales' },
  { href: '/customers', label: 'Customers' },
  { href: '/finance', label: 'Finance' },
  { href: '/returns', label: 'Returns' },
  { href: '/admin', label: 'Admin' },
  { href: '/purchases', label: 'Purchases' },
  { href: '/settings', label: 'Settings' }
];
