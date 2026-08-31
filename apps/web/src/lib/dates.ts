const dateKeyFormatter = new Map<string, Intl.DateTimeFormat>();
export const TRIFECTA_TIME_ZONE = "Asia/Dubai";

export function todayInTimezone(timezone: string, now = new Date()): string {
  let formatter = dateKeyFormatter.get(timezone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    dateKeyFormatter.set(timezone, formatter);
  }
  const parts = Object.fromEntries(formatter.formatToParts(now).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function dateKey(year: number, monthIndex: number, day: number): string {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function calendarCells(year: number, monthIndex: number): Array<number | null> {
  const firstWeekday = new Date(Date.UTC(year, monthIndex, 1)).getUTCDay();
  const days = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate();
  return [...Array<null>(firstWeekday).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
}

export function formatMoney(amountMinor: number, currency: string, locale = "en-AE"): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(amountMinor / 100);
}

export function formatSchedule(start: string, end: string, timezone: string, locale = "en-AE"): string {
  const day = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(start));
  const time = new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
  });
  return `${day}, ${time.format(new Date(start))}–${time.format(new Date(end))}`;
}
