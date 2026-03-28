import { PageShell } from '@/components/ui/page-shell';
import { ReturnsWorkspace } from '@/components/commerce/returns-workspace';

export default function ReturnsPage() {
  return (
    <PageShell title="Returns" description="Start from completed orders, validate eligible quantities, restock sellable items, and record refund payments explicitly.">
      <ReturnsWorkspace />
    </PageShell>
  );
}
