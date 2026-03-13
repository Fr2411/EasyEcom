import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function PurchasesPage() {
  return (
    <PageShell title="Purchases" description="Record stock-in purchases with tenant-safe inventory and finance impact.">
      <ResetPlaceholder moduleName="Purchases" />
    </PageShell>
  );
}
