import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function CatalogPage() {
  return (
    <PageShell title="Catalog" description="Catalog content has been cleared so we can rebuild products and variants from scratch.">
      <ResetPlaceholder moduleName="Catalog" />
    </PageShell>
  );
}
