import { redirect } from 'next/navigation';

export default function InventoryProductsLegacyPage() {
  redirect('/products-stock?mode=inventory');
}
