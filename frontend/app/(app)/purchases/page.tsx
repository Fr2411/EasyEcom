import { PageShell } from '@/components/ui/page-shell';
import { PurchasesWorkspace } from '@/components/purchases/purchases-workspace';

export default function PurchasesPage() {
  return (
    <PageShell
      title="Purchases"
      description="Manage purchase-order visibility here while inventory receipt remains inside the canonical variant-level receive-stock workflow."
    >
      <PurchasesWorkspace />
    </PageShell>
  );
}
