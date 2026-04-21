import { redirect } from 'next/navigation';

function firstParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value[0] ?? '';
  return value ?? '';
}

export default function ProductsStockPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const params = new URLSearchParams();
  const query = firstParam(searchParams.q).trim();
  if (query) {
    params.set('q', query);
  }
  const tab = firstParam(searchParams.tab).trim();
  if (tab) {
    params.set('tab', tab);
  }
  const suffix = params.toString() ? `?${params.toString()}` : '';
  redirect(`/inventory${suffix}`);
}
