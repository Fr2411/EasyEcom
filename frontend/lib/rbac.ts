const ROLE_PAGE_ACCESS: Record<string, string[]> = {
  SUPER_ADMIN: ['Dashboard', 'Catalog', 'Inventory', 'Sales', 'Customers', 'AI Assistant', 'Automation', 'Finance', 'Returns', 'Billing', 'Reports', 'Admin', 'Settings'],
  CLIENT_OWNER: ['Dashboard', 'Catalog', 'Inventory', 'Sales', 'Customers', 'AI Assistant', 'Automation', 'Finance', 'Returns', 'Billing', 'Reports', 'Settings'],
  CLIENT_STAFF: ['Dashboard', 'Catalog', 'Inventory', 'Sales', 'Customers', 'AI Assistant', 'Automation', 'Returns', 'Settings'],
  FINANCE_STAFF: ['Dashboard', 'Automation', 'Finance', 'Returns', 'Reports', 'Settings'],
};

const MANDATORY_ROLE_PAGE_ACCESS: Record<string, string[]> = {};

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

export function canSeePageInNavigation(
  userRoles: string[] | undefined,
  pageLabel: string,
) {
  const mandatoryPages = userRoles?.flatMap((role) => MANDATORY_ROLE_PAGE_ACCESS[role] ?? []) ?? [];
  if (mandatoryPages.includes(pageLabel)) {
    return true;
  }

  if (!userRoles?.length) {
    return false;
  }

  return userRoles.some((role) => ROLE_PAGE_ACCESS[role]?.includes(pageLabel));
}

export function isSuperAdmin(userRoles: string[] | undefined) {
  return Boolean(userRoles?.includes('SUPER_ADMIN'));
}
