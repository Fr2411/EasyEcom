import { PageShell } from '@/components/ui/page-shell';
import { ReturnsWorkspace } from '@/components/commerce/returns-workspace';

export default function ReturnsPage() {
  return (
    <PageShell title="Returns" description="Start from completed orders, validate eligible quantities, and restock only what becomes sellable again.">
      <ReturnsWorkspace />
    </PageShell>
  );
}
