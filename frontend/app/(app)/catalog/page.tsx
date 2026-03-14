import { PageShell } from '@/components/ui/page-shell';
import { CatalogWorkspace } from '@/components/commerce/catalog-workspace';

export default function CatalogPage() {
  return (
    <PageShell title="Catalog" description="Manage parent products and saleable variants with stock-aware search.">
      <CatalogWorkspace />
    </PageShell>
  );
}
