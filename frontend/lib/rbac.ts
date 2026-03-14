const ROLE_PAGE_ACCESS: Record<string, string[]> = {
  SUPER_ADMIN: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Customers', 'Finance', 'Returns', 'Reports', 'Admin', 'Settings'],
  CLIENT_OWNER: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Finance', 'Returns', 'Reports', 'Settings'],
  CLIENT_STAFF: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Returns', 'Settings'],
  FINANCE_STAFF: ['Home', 'Dashboard', 'Finance', 'Returns', 'Reports', 'Settings'],
};

export function canAccessPage(
  userRoles: string[] | undefined,
  pageLabel: string,
  allowedPages?: string[] | undefined,
) {
  if (allowedPages?.length) {
    return allowedPages.includes(pageLabel);
  }

  if (!userRoles?.length) {
    return false;
  }

  return userRoles.some((role) => ROLE_PAGE_ACCESS[role]?.includes(pageLabel));
}

export function isSuperAdmin(userRoles: string[] | undefined) {
  return Boolean(userRoles?.includes('SUPER_ADMIN'));
}
