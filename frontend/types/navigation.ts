export type NavigationItem = {
  href: string;
  label: string;
};

export const NAV_ITEMS: NavigationItem[] = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/products-stock', label: 'Products & Stock' },
  { href: '/sales', label: 'Sales' },
  { href: '/customers', label: 'Customers' },
  { href: '/purchases', label: 'Purchases' },
  { href: '/settings', label: 'Settings' }
];
