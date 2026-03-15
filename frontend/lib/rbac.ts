const ROLE_PAGE_ACCESS: Record<string, string[]> = {
  SUPER_ADMIN: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'Customers', 'Finance', 'Returns', 'Reports', 'Admin', 'Settings'],
  CLIENT_OWNER: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'Finance', 'Returns', 'Reports', 'Settings'],
  CLIENT_STAFF: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'Returns', 'Settings'],
  FINANCE_STAFF: ['Home', 'Dashboard', 'Finance', 'Returns', 'Reports', 'Settings'],
};

const MANDATORY_ROLE_PAGE_ACCESS: Record<string, string[]> = {
  CLIENT_OWNER: ['Sales Agent'],
};

export function canAccessPage(
  userRoles: string[] | undefined,
  pageLabel: string,
  allowedPages?: string[] | undefined,
) {
  const mandatoryPages = userRoles?.flatMap((role) => MANDATORY_ROLE_PAGE_ACCESS[role] ?? []) ?? [];
  if (mandatoryPages.includes(pageLabel)) {
    return true;
  }

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
