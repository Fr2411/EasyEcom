const ROLE_PAGE_ACCESS: Record<string, string[]> = {
  SUPER_ADMIN: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'AI Review', 'Automation', 'Customers', 'Finance', 'Returns', 'Reports', 'Admin', 'Settings'],
  CLIENT_OWNER: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'AI Review', 'Automation', 'Finance', 'Returns', 'Reports', 'Settings'],
  CLIENT_STAFF: ['Home', 'Dashboard', 'Catalog', 'Inventory', 'Purchases', 'Sales', 'Sales Agent', 'AI Review', 'Automation', 'Returns', 'Settings'],
  FINANCE_STAFF: ['Home', 'Dashboard', 'Automation', 'Finance', 'Returns', 'Reports', 'Settings'],
};

const MANDATORY_ROLE_PAGE_ACCESS: Record<string, string[]> = {
  CLIENT_OWNER: ['Sales Agent', 'AI Review'],
};

export function canAccessPage(
  userRoles: string[] | undefined,
  pageLabel: string,
  allowedPages?: string[] | undefined,
) {
  if (pageLabel === 'AI Review') {
    if (allowedPages?.includes('AI Review') || allowedPages?.includes('Sales Agent')) {
      return true;
    }
    return userRoles?.some((role) => ROLE_PAGE_ACCESS[role]?.includes('AI Review') || ROLE_PAGE_ACCESS[role]?.includes('Sales Agent')) ?? false;
  }

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
