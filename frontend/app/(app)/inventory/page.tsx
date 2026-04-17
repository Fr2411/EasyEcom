import { PageShell } from '@/components/ui/page-shell';
import { InventoryWorkspace } from '@/components/commerce/inventory-workspace';

export default function InventoryPage() {
  return (
    <PageShell title="Inventory" description="Find or create products from Receive Stock, track availability, and keep every movement auditable."
      hideHeader
    >
      <InventoryWorkspace />
    </PageShell>
  );
}
