import { InventoryOpsWorkspace } from '@/components/commerce/inventory-ops-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function InventoryPage() {
  return (
    <PageShell
      title="Inventory"
      description="Track available variant stock and run fast stock operations: receive, adjust, sell, or open catalog context."
      hideHeader
    >
      <InventoryOpsWorkspace />
    </PageShell>
  );
}
