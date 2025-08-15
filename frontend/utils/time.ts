// utils/time.ts
export function parsePgTimestamptz(ts: string): Date {
  // Accept "YYYY-MM-DD HH:MM:SS+00" or ISO; normalize to ISO with "T"
  const normalized = ts.replace(' ', 'T');
  return new Date(normalized);
}

export function isSameLocalDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function isTodayLocal(ts: string) {
  const d = parsePgTimestamptz(ts);
  return isSameLocalDay(d, new Date());
}

export function isTomorrowLocal(ts: string) {
  const d = parsePgTimestamptz(ts);
  const t = new Date();
  const tomorrow = new Date(t.getFullYear(), t.getMonth(), t.getDate() + 1);
  return isSameLocalDay(d, tomorrow);
}

export function dayLabel(ts: string) {
  if (isTodayLocal(ts)) return 'Today';
  if (isTomorrowLocal(ts)) return 'Tomorrow';
  return 'Upcoming';
}

export function formatLocalDate(ts: string, opts?: Intl.DateTimeFormatOptions) {
  const d = parsePgTimestamptz(ts);
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    ...opts,
  }).format(d);
}

export function formatLocalTime(ts: string, opts?: Intl.DateTimeFormatOptions) {
  const d = parsePgTimestamptz(ts);
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...opts,
  }).format(d);
}

export function formatLocalDateTime(
  ts: string,
  opts?: Intl.DateTimeFormatOptions
) {
  const d = parsePgTimestamptz(ts);
  const formatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZoneName: 'short',
    ...opts,
  });
  return formatter.format(d);
}