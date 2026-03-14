export function numberFromString(value: string | null | undefined) {
  if (value === null || value === undefined || value === '') return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}


export function formatMoney(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return 'Not set';
  return numberFromString(String(value)).toFixed(2);
}


export function formatPercent(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return 'Not set';
  return `${numberFromString(String(value)).toFixed(2)}%`;
}


export function formatQuantity(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '0.000';
  return numberFromString(String(value)).toFixed(3);
}


export function formatDateTime(value: string | null | undefined) {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString();
}
