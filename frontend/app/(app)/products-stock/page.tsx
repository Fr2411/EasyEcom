import { redirect } from 'next/navigation';

export default function ProductsStockPage() {
  redirect('/inventory?tab=receive');
}
