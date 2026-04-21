import { CatalogLibraryWorkspace } from '@/components/commerce/catalog-library-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function CatalogPage() {
  return (
    <PageShell
      title="Catalog"
      description="Manage product identity in one place. Add or edit product cards, then handle stock operations from Inventory."
      hideHeader
    >
      <CatalogLibraryWorkspace />
    </PageShell>
  );
}
