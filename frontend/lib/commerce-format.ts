export function numberFromString(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}


export function formatMoney(value: string | number) {
  return numberFromString(String(value)).toFixed(2);
}


export function formatQuantity(value: string | number) {
  return numberFromString(String(value)).toFixed(3);
}


export function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString();
}
