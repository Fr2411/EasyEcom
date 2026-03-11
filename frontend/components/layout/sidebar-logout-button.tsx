'use client';

import { LogOut } from 'lucide-react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';

export function SidebarLogoutButton() {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    if (isLoggingOut) {
      return;
    }

    setIsLoggingOut(true);
    try {
      await logout();
    } catch {
      // Ignore logout API errors and still force redirect to login.
    } finally {
      router.replace('/login');
      router.refresh();
      setIsLoggingOut(false);
    }
  };

  return (
    <button
      type="button"
      className="nav-link nav-link-button"
      onClick={handleLogout}
      disabled={isLoggingOut}
    >
      <LogOut size={16} aria-hidden="true" />
      <span>{isLoggingOut ? 'Logging out…' : 'Log out'}</span>
    </button>
  );
}
