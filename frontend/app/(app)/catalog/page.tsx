import { redirect } from 'next/navigation';

function firstParam(value: string | string[] | undefined) {
  if (Array.isArray(value)) return value[0] ?? '';
  return value ?? '';
}

export default function CatalogPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const query = firstParam(searchParams.q).trim();
  const params = new URLSearchParams();
  if (query) {
    params.set('q', query);
  }
  params.set('mode', 'catalog');
  const suffix = params.toString() ? `?${params.toString()}` : '';
  redirect(`/products-stock${suffix}`);
}
