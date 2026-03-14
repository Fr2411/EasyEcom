import { redirect } from 'next/navigation';

export default function PurchasesPage() {
  redirect('/inventory?tab=receive');
}
