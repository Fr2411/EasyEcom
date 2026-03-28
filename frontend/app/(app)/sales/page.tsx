import { PageShell } from '@/components/ui/page-shell';
import { SalesWorkspace } from '@/components/commerce/sales-workspace';

export default function SalesPage() {
  return (
    <PageShell title="Sales" description="Create order-driven sales, reserve stock truthfully, and fulfill with finance status surfaced after posting.">
      <SalesWorkspace />
    </PageShell>
  );
}
