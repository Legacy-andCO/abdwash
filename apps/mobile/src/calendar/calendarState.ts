import type { CalendarJob } from "../lib";

const iso = (value: Date) => value.toISOString().slice(0, 10);

export function monthWindow(month: string) {
  const [year, monthIndex] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, monthIndex - 1, 1));
  const last = new Date(Date.UTC(year, monthIndex, 0));
  const start = new Date(first);
  start.setUTCDate(first.getUTCDate() - first.getUTCDay());
  const end = new Date(last);
  end.setUTCDate(last.getUTCDate() + (6 - last.getUTCDay()));
  return { start: iso(start), end: iso(end) };
}

export function calendarDays(start: string, end: string) {
  const result: string[] = [];
  const cursor = new Date(`${start}T00:00:00Z`);
  const finish = new Date(`${end}T00:00:00Z`);
  while (cursor <= finish) {
    result.push(iso(cursor));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return result;
}

export function shiftMonth(month: string, amount: number) {
  const [year, monthIndex] = month.split("-").map(Number);
  const value = new Date(Date.UTC(year, monthIndex - 1 + amount, 1));
  return value.toISOString().slice(0, 7);
}

export function jobsByDate(jobs: CalendarJob[]) {
  const grouped = new Map<string, CalendarJob[]>();
  for (const job of jobs) {
    const values = grouped.get(job.local_date) ?? [];
    values.push(job);
    grouped.set(job.local_date, values);
  }
  for (const values of grouped.values())
    values.sort((a, b) => a.scheduled_start.localeCompare(b.scheduled_start));
  return grouped;
}
