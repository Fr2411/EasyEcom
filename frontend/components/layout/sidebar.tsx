import Image from 'next/image';

import { NAV_ITEMS } from '@/types/navigation';
import { NavItem } from '@/components/ui/nav-item';
import { SidebarLogoutButton } from '@/components/layout/sidebar-logout-button';

const groupedNavigation = NAV_ITEMS.reduce<Record<string, typeof NAV_ITEMS>>((acc, item) => {
  if (!acc[item.group]) {
    acc[item.group] = [];
  }
  acc[item.group].push(item);
  return acc;
}, {});

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="brand-block">
        <Image
          src="/brand/easy-ecom-logo.svg"
          alt="Easy-Ecom"
          width={310}
          height={85}
          className="brand-logo"
          priority
        />
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
