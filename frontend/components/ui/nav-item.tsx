'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NavigationItem } from '@/types/navigation';

export function NavItem({ item }: { item: NavigationItem }) {
  const pathname = usePathname();
  const isActive = pathname === item.href;

  return (
    <Link href={item.href} className={isActive ? 'nav-link active' : 'nav-link'}>
      <span>{item.label}</span>
    </Link>
  );
}
