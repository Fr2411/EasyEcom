import { PageShell } from '@/components/ui/page-shell';
import { PurchasesWorkspace } from '@/components/purchases/purchases-workspace';

export default function PurchasesPage() {
  return (
    <PageShell
      title="Purchases"
      description="Track purchase-order progress here. Receive incoming stock from the Inventory page when deliveries arrive."
      hideHeader
    >
      <PurchasesWorkspace />
    </PageShell>
  );
}
