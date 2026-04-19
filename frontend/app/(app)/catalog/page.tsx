import { PageShell } from '@/components/ui/page-shell';
import { CatalogWorkspace } from '@/components/commerce/catalog-workspace';

export default function CatalogPage() {
  return (
    <PageShell
      title="Catalog"
      description="Manage product details and their sellable variants. Use Receive Stock for daily stock intake."
      hideHeader
    >
      <CatalogWorkspace />
    </PageShell>
  );
}
