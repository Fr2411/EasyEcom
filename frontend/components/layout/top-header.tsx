'use client';

import { useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';

export function TopHeader() {
  const router = useRouter();

  return (
    <header className="top-header">
      <div>
        <p className="eyebrow">EasyEcom</p>
        <p className="header-title">Operations Workspace</p>
      </div>
      <div className="header-actions">
        <div className="header-pill">Catalog + Inventory</div>
        <button
          onClick={async () => {
            await logout();
            router.replace('/login');
          }}
        >
          Logout
        </button>
      </div>
    </header>
  );
}
