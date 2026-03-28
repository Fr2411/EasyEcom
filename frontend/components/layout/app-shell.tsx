'use client';

import { useEffect, useState } from 'react';
import { Sidebar } from '@/components/layout/sidebar';
import { TopHeader } from '@/components/layout/top-header';

const SIDEBAR_STORAGE_KEY = 'easy-ecom.sidebar.collapsed';

function readSidebarPreference() {
  if (typeof window === 'undefined' || typeof window.localStorage?.getItem !== 'function') {
    return false;
  }
  return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1';
}

function writeSidebarPreference(collapsed: boolean) {
  if (typeof window === 'undefined' || typeof window.localStorage?.setItem !== 'function') {
    return;
  }
  window.localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? '1' : '0');
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => readSidebarPreference());

  useEffect(() => {
    writeSidebarPreference(sidebarCollapsed);
  }, [sidebarCollapsed]);

  return (
    <div className={sidebarCollapsed ? 'shell sidebar-collapsed' : 'shell'}>
      <div className="shell-backdrop" aria-hidden="true">
        <span className="shell-orb shell-orb-a" />
        <span className="shell-orb shell-orb-b" />
        <span className="shell-grid" />
      </div>
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((current) => !current)}
      />
      <div className="content-pane">
        <TopHeader />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
