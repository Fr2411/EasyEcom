import { redirect } from 'next/navigation';

export default function InventoryProductsLegacyPage() {
  redirect('/inventory?tab=receive');
}
