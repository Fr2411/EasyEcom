import { PageShell } from '@/components/ui/page-shell';
import { InventoryWorkspace } from '@/components/commerce/inventory-workspace';

export default function InventoryPage() {
  return (
    <PageShell title="Inventory" description="Track available stock, receive new inventory, and keep every movement auditable.">
      <InventoryWorkspace />
    </PageShell>
  );
}
