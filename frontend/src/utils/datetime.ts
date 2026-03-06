function parseServerDateTime(value: string): Date {
  const hasTimezone = /[zZ]|[+\-]\d{2}:\d{2}$/.test(value);
  const normalized = hasTimezone ? value : `${value}Z`;
  return new Date(normalized);
}

export function formatServerDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = parseServerDateTime(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}:${pad(date.getSeconds())}`;
}
