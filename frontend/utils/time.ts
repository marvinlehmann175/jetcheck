// utils/time.ts
export function parsePgTimestamptz(ts: string): Date {
  // Accept "YYYY-MM-DD HH:MM:SS+00" or ISO; normalize to ISO with "T"
  const normalized = ts.replace(" ", "T");
  return new Date(normalized);
}

export function formatLocal(
  ts: string,
  tz?: string,
  opts?: Intl.DateTimeFormatOptions
) {
  const d = parsePgTimestamptz(ts);
  return new Intl.DateTimeFormat(undefined, {
    timeZone: tz || undefined,
    ...opts,
  }).format(d);
}

export function shortTz(ts: string, tz?: string) {
  // e.g. "CEST"
  return formatLocal(ts, tz, {
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  })
    .split(" ")
    .pop();
}

export function dayLabel(ts: string, tz?: string) {
  const d = parsePgTimestamptz(ts);
  const now = new Date();
  const ymd = (x: Date) =>
    new Intl.DateTimeFormat("en-CA", {
      timeZone: tz || undefined,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(x); // YYYY-MM-DD

  const today = ymd(now);
  const tomorrow = ymd(new Date(now.getTime() + 24 * 3600 * 1000));
  const dateStr = ymd(d);

  if (dateStr === today) return "Today";
  if (dateStr === tomorrow) return "Tomorrow";
  return "Upcoming";
}

export function formatLocalDate(ts: string, tz?: string) {
  return formatLocal(ts, tz, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function formatLocalTimeWithTz(ts: string, tz?: string) {
  // returns "08:50 CEST"
  const d = parsePgTimestamptz(ts);
  const parts = new Intl.DateTimeFormat(undefined, {
    timeZone: tz || undefined,
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
    hour12: false,
  }).formatToParts(d);

  const hh = parts.find(p => p.type === "hour")?.value ?? "";
  const mm = parts.find(p => p.type === "minute")?.value ?? "";
  const tzs = parts.find(p => p.type === "timeZoneName")?.value ?? "";
  return `${hh}:${mm} ${tzs}`.trim();
}