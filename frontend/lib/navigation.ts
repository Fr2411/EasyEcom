import type { SessionUser } from '@/lib/api/auth';
import { canSeePageInNavigation } from '@/lib/rbac';
import { NAV_ITEMS } from '@/types/navigation';

export function redirectToExternalUrl(url: string) {
  if (typeof window === 'undefined') {
    return;
  }

  window.location.assign(url);
}

export function getVisibleNavigationItems(user: SessionUser | null | undefined) {
  return NAV_ITEMS.filter((item) => {
    if (item.label === 'Catalog' && !user?.roles?.includes('SUPER_ADMIN')) {
      return false;
    }
    return canSeePageInNavigation(user?.roles, item.label);
  });
}

export function getMobilePrimaryItems(user: SessionUser | null | undefined) {
  const visibleItems = getVisibleNavigationItems(user);
  const preferredOrder = ['/dashboard', '/inventory', '/sales', '/returns'];
  const primary = preferredOrder
    .map((href) => visibleItems.find((item) => item.href === href))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  if (primary.length >= 4) {
    return primary.slice(0, 4);
  }

  for (const item of visibleItems) {
    if (primary.some((entry) => entry.href === item.href) || item.href === '/home') {
      continue;
    }
    primary.push(item);
    if (primary.length === 4) {
      break;
    }
  }

  return primary;
}
