/**
 * Timezone / datetime helpers for the admin portal.
 *
 * Convention: the backend stores and returns UTC. The UI lets the user pick a
 * display timezone; we convert UTC -> that timezone for display, and send local
 * wall-clock strings (from <input type="datetime-local">) plus the tz name to
 * the backend, which interprets them in that timezone.
 */

export const COMMON_TIMEZONES: string[] = [
  'UTC',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Singapore',
  'Asia/Kolkata',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Chicago',
  'America/Los_Angeles',
  'Australia/Sydney',
];

/** Best-effort browser timezone, falling back to Asia/Shanghai. */
export function getDefaultTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
  } catch {
    return 'Asia/Shanghai';
  }
}

/** Normalize a backend UTC datetime string to one parseable as UTC. */
function asUtcDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  // Backend serializes naive UTC datetimes without an offset; treat as UTC.
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value);
  const iso = hasTz ? value : `${value}Z`;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

/** Format a backend UTC datetime string for display in the given timezone. */
export function formatUtcDisplay(
  value: string | null | undefined,
  tz: string
): string {
  const d = asUtcDate(value);
  if (!d) return '';
  try {
    return new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: tz,
    }).format(d);
  } catch {
    return d.toISOString();
  }
}

/** Today's date (YYYY-MM-DD) in the given timezone. */
export function todayInTz(tz: string): string {
  try {
    return new Intl.DateTimeFormat('en-CA', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      timeZone: tz,
    }).format(new Date());
  } catch {
    return new Date().toISOString().slice(0, 10);
  }
}

/** Shift a YYYY-MM-DD day string by ``delta`` days. */
export function shiftDay(day: string, delta: number): string {
  const [y, m, d] = day.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + delta);
  return dt.toISOString().slice(0, 10);
}

/** Default datetime-local value (now) as YYYY-MM-DDTHH:MM. */
export function nowLocalInput(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value N hours ago. */
export function hoursAgoLocalInput(hours: number): string {
  const d = new Date(Date.now() - hours * 3600 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
