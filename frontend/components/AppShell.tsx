'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { PropsWithChildren, useEffect, useState } from 'react';
import { SessionUser } from '../lib/api';

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/products-stock', label: 'Products & Stock' },
  { href: '/sales', label: 'Sales' }
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem('easy_ecom_user');
    if (!raw && pathname !== '/login') {
      router.push('/login');
      return;
    }
    if (raw) setUser(JSON.parse(raw));
  }, [pathname, router]);

  if (pathname === '/login') return <>{children}</>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', minHeight: '100vh' }}>
      <aside style={{ padding: 16, borderRight: '1px solid #ddd' }}>
        <h3>EasyEcom</h3>
        <div style={{ marginBottom: 16 }}>{user?.email}</div>
        {links.map((l) => (
          <div key={l.href} style={{ marginBottom: 8 }}>
            <Link href={l.href}>{l.label}</Link>
          </div>
        ))}
      </aside>
      <main style={{ padding: 16 }}>{children}</main>
    </div>
  );
}
