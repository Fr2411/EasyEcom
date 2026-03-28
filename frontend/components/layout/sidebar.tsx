'use client';

import { Building2, Mail, PanelLeftClose, PanelLeftOpen, UserRound } from 'lucide-react';
import { NAV_GROUP_ORDER, NAV_ITEMS } from '@/types/navigation';
import { NavItem } from '@/components/ui/nav-item';
import { SidebarLogoutButton } from '@/components/layout/sidebar-logout-button';
import { EasyEcomLogo } from '@/components/branding/easy-ecom-logo';
import { useAuth } from '@/components/auth/auth-provider';
import { canAccessPage } from '@/lib/rbac';

export function Sidebar({
  collapsed = false,
  onToggle,
}: {
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  const { user } = useAuth();
  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.label === 'Catalog' && !user?.roles?.includes('SUPER_ADMIN')) {
      return false;
    }
    return canAccessPage(user?.roles, item.label, user?.allowed_pages);
  });
  const groupedNavigation = NAV_GROUP_ORDER.map((group) => ({
    group,
    items: visibleItems.filter((item) => item.group === group),
  })).filter(({ items }) => items.length > 0);
  const workspaceName = user?.business_name?.trim() || (user?.roles?.includes('SUPER_ADMIN') ? 'Easy-Ecom Internal' : 'Business workspace');
  const primaryRole = user?.roles?.[0]?.replaceAll('_', ' ') || 'Workspace user';
  const quickStatus = user?.roles?.includes('SUPER_ADMIN') ? 'Platform control' : 'Tenant workspace';
  const navCount = visibleItems.length;

  return (
    <aside className={collapsed ? 'sidebar sidebar-collapsed' : 'sidebar'} aria-label="Primary">
      <div className="brand-block">
        <div className="brand-badge-row">
          <span className="brand-badge">{quickStatus}</span>
          <span className="brand-badge muted">{navCount} modules</span>
        </div>
        <div className="brand-top-row">
          <div className="brand-logo-wrap">
            <EasyEcomLogo
              className="easyecom-logo easyecom-logo-sidebar"
              imageClassName="easyecom-logo-image easyecom-logo-sidebar"
            />
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={onToggle}
            aria-label={collapsed ? 'Open sidebar' : 'Minimize sidebar'}
            title={collapsed ? 'Open sidebar' : 'Minimize sidebar'}
          >
            {collapsed ? <PanelLeftOpen size={16} aria-hidden="true" /> : <PanelLeftClose size={16} aria-hidden="true" />}
          </button>
        </div>
        <h1 className="brand-title">Operations Hub</h1>
        <p className="brand-subtitle">Unified commerce command center for daily operations, control, and exceptions.</p>
        <div className="sidebar-user-card">
          <div className="sidebar-user-row">
            <Building2 size={15} aria-hidden="true" />
            <div>
              <p className="eyebrow">Business</p>
              <strong>{workspaceName}</strong>
            </div>
          </div>
          <div className="sidebar-user-row">
            <UserRound size={15} aria-hidden="true" />
            <div>
              <p className="eyebrow">User</p>
              <span>{user?.name || 'Unknown user'}</span>
              <small>{primaryRole}</small>
            </div>
          </div>
          <div className="sidebar-user-row">
            <Mail size={15} aria-hidden="true" />
            <div>
              <p className="eyebrow">Email</p>
              <span>{user?.email || 'No email available'}</span>
            </div>
          </div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {groupedNavigation.map(({ group, items }) => (
          <section key={group} className="nav-group" aria-label={group}>
            <h2>{group}</h2>
            <ul className="nav-list">
              {items.map((item) => (
                <li key={item.href}>
                  <NavItem item={item} collapsed={collapsed} />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>
      <footer className="sidebar-footer">
        <p className="eyebrow">Workspace</p>
        <strong>Production Mode</strong>
        <p className="sidebar-footer-copy">Tenant-safe workflows, variant-level stock truth, and auditable actions.</p>
        <SidebarLogoutButton />
      </footer>
    </aside>
  );
}
