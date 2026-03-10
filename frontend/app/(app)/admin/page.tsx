import { PageShell } from '@/components/ui/page-shell';
import { AdminWorkspace } from '@/components/admin/admin-workspace';

export default function AdminPage() {
  return (
    <PageShell title="Admin & Roles" description="Manage tenant users, roles, and account activation safely.">
      <AdminWorkspace />
    </PageShell>
  );
}
