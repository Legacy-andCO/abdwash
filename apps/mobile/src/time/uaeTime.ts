export const UAE_TIME_ZONE = "Asia/Dubai";

type TemporalValue = Date | string | number;

const datePartsFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: UAE_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timePartsFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: UAE_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function parts(
  formatter: Intl.DateTimeFormat,
  value: TemporalValue,
): Record<string, string> {
  return Object.fromEntries(
    formatter
      .formatToParts(value instanceof Date ? value : new Date(value))
      .map((part) => [part.type, part.value]),
  );
}

export function uaeDateKey(value: TemporalValue = new Date()): string {
  const valueParts = parts(datePartsFormatter, value);
  return `${valueParts.year}-${valueParts.month}-${valueParts.day}`;
}

export function uaeTimeValue(value: TemporalValue): string {
  const valueParts = parts(timePartsFormatter, value);
  return `${valueParts.hour}:${valueParts.minute}`;
}

export function uaeAppointmentParts(value: TemporalValue): {
  date: string;
  time: string;
} {
  return { date: uaeDateKey(value), time: uaeTimeValue(value) };
}

export function formatUaeTime(
  value: TemporalValue,
  locale?: Intl.LocalesArgument,
): string {
  return new Intl.DateTimeFormat(locale, {
    timeZone: UAE_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  }).format(value instanceof Date ? value : new Date(value));
}

export function formatUaeDate(
  value: TemporalValue,
  locale?: Intl.LocalesArgument,
  options: Intl.DateTimeFormatOptions = {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  },
): string {
  return new Intl.DateTimeFormat(locale, {
    ...options,
    timeZone: UAE_TIME_ZONE,
  }).format(value instanceof Date ? value : new Date(value));
}

export function formatUaeDateTime(
  value: TemporalValue,
  locale?: Intl.LocalesArgument,
): string {
  return new Intl.DateTimeFormat(locale, {
    timeZone: UAE_TIME_ZONE,
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(value instanceof Date ? value : new Date(value));
}

export function wallDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 12);
}

export function addUaeDays(day: string, amount: number): string {
  const [year, month, date] = day.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1, date + amount));
  return value.toISOString().slice(0, 10);
}

export function formatWallClockTime(
  value: string,
  locale?: Intl.LocalesArgument,
): string {
  const [hour, minute] = value.split(":").map(Number);
  return new Intl.DateTimeFormat(locale, {
    timeZone: "UTC",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(Date.UTC(2000, 0, 1, hour, minute)));
}
