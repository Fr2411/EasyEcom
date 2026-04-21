import { PageShell } from '@/components/ui/page-shell';
import { ProductsStockWorkspace } from '@/components/commerce/products-stock-workspace';

export default function ProductsStockPage() {
  return (
    <PageShell
      title="Products & Stock"
      description="Unified workflow for finding products, editing variants, receiving stock, and recording adjustments."
      hideHeader
    >
      <ProductsStockWorkspace />
    </PageShell>
  );
}
