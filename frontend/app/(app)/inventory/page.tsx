import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function InventoryPage() {
  return (
    <PageShell title="Inventory" description="Track stock on-hand and audit every movement with tenant-safe inventory operations.">
      <ResetPlaceholder moduleName="Inventory" />
    </PageShell>
  );
}
