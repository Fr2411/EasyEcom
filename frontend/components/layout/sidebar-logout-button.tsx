'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { logout } from '@/lib/api/auth';
import { useAuth } from '@/components/auth/auth-provider';

export function SidebarLogoutButton() {
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const { clearAuth } = useAuth();

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
      clearAuth();
      router.replace('/login');
      router.refresh();
      setIsLoggingOut(false);
    }
  };

  return (
    <button
      type="button"
      className="sidebar-logout-btn"
      onClick={handleLogout}
      disabled={isLoggingOut}
    >
      {isLoggingOut ? 'Logging out…' : 'Log out'}
    </button>
  );
}
