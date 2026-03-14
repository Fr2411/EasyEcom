'use client';

import { NAV_ITEMS } from '@/types/navigation';
import { NavItem } from '@/components/ui/nav-item';
import { SidebarLogoutButton } from '@/components/layout/sidebar-logout-button';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';
import { useAuth } from '@/components/auth/auth-provider';
import { canAccessPage } from '@/lib/rbac';

export function Sidebar() {
  const { user } = useAuth();
  const visibleItems = NAV_ITEMS.filter((item) => canAccessPage(user?.roles, item.label));
  const groupedNavigation = visibleItems.reduce<Record<string, typeof NAV_ITEMS>>((acc, item) => {
    if (!acc[item.group]) {
      acc[item.group] = [];
    }
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="brand-block">
        <div className="brand-logo-wrap">
          <EasyEcomLogo
            className="easyecom-logo easyecom-logo-sidebar"
            imageClassName="easyecom-logo-image easyecom-logo-sidebar"
          />
        </div>
        <h1 className="brand-title">Operations Hub</h1>
        <p className="brand-subtitle">Business Command Center</p>
      </div>
      <nav className="sidebar-nav">
        {Object.entries(groupedNavigation).map(([group, items]) => (
          <section key={group} className="nav-group" aria-label={group}>
            <h2>{group}</h2>
            <ul className="nav-list">
              {items.map((item) => (
                <li key={item.href}>
                  <NavItem item={item} />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>
      <footer className="sidebar-footer">
        <p className="eyebrow">Workspace</p>
        <strong>Production Mode</strong>
        <SidebarLogoutButton />
      </footer>
    </aside>
  );
}
