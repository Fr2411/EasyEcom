import { NAV_ITEMS } from '@/types/navigation';
import { NavItem } from '@/components/ui/nav-item';

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="brand-block">
        <p className="eyebrow">EasyEcom</p>
        <h1 className="brand-title">Operations Hub</h1>
      </div>
      <nav>
        <ul className="nav-list">
          {NAV_ITEMS.map((item) => (
            <li key={item.href}>
              <NavItem item={item} />
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
}
