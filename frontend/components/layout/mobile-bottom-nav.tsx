'use client';

import Link from 'next/link';
import { Menu } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/components/auth/auth-provider';
import { getNavigationIcon } from '@/components/ui/nav-item';
import { getMobilePrimaryItems } from '@/lib/navigation';

export function MobileBottomNav({ onOpenMenu }: { onOpenMenu: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const primaryItems = getMobilePrimaryItems(user);

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile navigation">
      {primaryItems.map((item) => {
        const Icon = getNavigationIcon(item.icon);
        const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={isActive ? 'mobile-bottom-link active' : 'mobile-bottom-link'}
            aria-current={isActive ? 'page' : undefined}
          >
            <Icon size={18} aria-hidden="true" />
            <span>{item.label}</span>
          </Link>
        );
      })}
      <button type="button" className="mobile-bottom-link" onClick={onOpenMenu} aria-label="Open navigation menu">
        <Menu size={18} aria-hidden="true" />
        <span>More</span>
      </button>
    </nav>
  );
}
