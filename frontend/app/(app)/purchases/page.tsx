import { PageShell } from '@/components/ui/page-shell';
import { PurchasesWorkspace } from '@/components/purchases/purchases-workspace';

export default function PurchasesPage() {
  return (
    <PageShell title="Purchases" description="Record stock-in purchases with tenant-safe inventory and finance impact.">
      <PurchasesWorkspace />
    </PageShell>
  );
}
