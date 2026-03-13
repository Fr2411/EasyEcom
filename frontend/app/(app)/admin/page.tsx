import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function AdminPage() {
  return (
    <PageShell title="Admin & Roles" description="Manage tenant users, roles, and account activation safely.">
      <ResetPlaceholder moduleName="Admin" />
    </PageShell>
  );
}
