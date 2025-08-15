'use client';

import { parsePgTimestamptz, formatLocalDate, formatLocalTime } from '@/utils/time';

type Props = {
  ts?: string | null;
  className?: string;
  mode?: 'date' | 'time'; // default renders 'time' here
};

export default function LocalTime({ ts, className, mode = 'time' }: Props) {
  if (!ts) return <span className={className}>—</span>;
  const d = parsePgTimestamptz(ts);
  const iso = d.toISOString();

  const text = mode === 'date' ? formatLocalDate(ts) : formatLocalTime(ts);

  return (
    <time dateTime={iso} title={`UTC: ${iso}`} className={className}>
      {text}
    </time>
  );
}