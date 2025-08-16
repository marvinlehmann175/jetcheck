// components/LocalTime.tsx
'use client';

import {
  parsePgTimestamptz,
  formatLocalDate,
  formatLocalTimeWithTz,
} from '@/utils/time';

type Props = {
  ts?: string | null;
  tz?: string | null;          // <-- NEW
  className?: string;
  stacked?: boolean;           // renders date over time
};

export default function LocalTime({ ts, tz, className, stacked }: Props) {
  if (!ts) return <span className={className}>—</span>;
  const d = parsePgTimestamptz(ts);
  const iso = d.toISOString(); // UTC ISO for machine-readability

  const dateStr = formatLocalDate(ts, tz || undefined);
  const timeStr = formatLocalTimeWithTz(ts, tz || undefined);

  if (stacked) {
    return (
      <time dateTime={iso} title={`UTC: ${iso}`} className={className}>
        <span className="flightcard__date">{dateStr}</span>
        <span className="flightcard__time">{timeStr}</span>
      </time>
    );
  }

  return (
    <time dateTime={iso} title={`UTC: ${iso}`} className={className}>
      {`${dateStr}, ${timeStr}`}
    </time>
  );
}