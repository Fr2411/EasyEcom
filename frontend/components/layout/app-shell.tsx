import { Sidebar } from '@/components/layout/sidebar';
import { TopHeader } from '@/components/layout/top-header';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <Sidebar />
      <div className="content-pane">
        <TopHeader />
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
