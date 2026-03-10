import { PageShell } from '@/components/ui/page-shell';
import { InventoryWorkspace } from '@/components/inventory/inventory-workspace';

export default function InventoryPage() {
  return (
    <PageShell title="Inventory" description="Track stock on-hand and audit every movement with tenant-safe inventory operations.">
      <InventoryWorkspace />
    </PageShell>
  );
}
