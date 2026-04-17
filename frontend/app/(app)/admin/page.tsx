import { PageShell } from '@/components/ui/page-shell';
import { AdminWorkspace } from '@/components/admin/admin-workspace';

export default function AdminPage() {
  return (
    <PageShell title="Super Admin Panel" description="Onboard tenants, manage their users, issue setup links, and protect access from one workspace."
      hideHeader
    >
      <AdminWorkspace />
    </PageShell>
  );
}
