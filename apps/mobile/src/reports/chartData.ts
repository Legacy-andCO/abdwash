import type { ReportPoint } from "../lib";
import { addUaeDays } from "../time/uaeTime";

export type ChartPoint = ReportPoint & { endDate: string };
export function reportChartData(series: ReportPoint[], start: string, end: string) {
  const count = Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1;
  if (!Number.isFinite(count) || count < 1 || count > 367) return [];
  const byDate = new Map(series.map(point => [point.date, point]));
  const grouped = new Map<string, ChartPoint>();
  for (let i = 0; i < count; i++) {
    const date = addUaeDays(start, i);
    const key = count > 90 ? date.slice(0, 7) : count > 31 ? addUaeDays(start, Math.floor(i / 7) * 7) : date;
    const value = byDate.get(date);
    const point = grouped.get(key) ?? { date, endDate: date, booked_sales_minor: 0, collected_revenue_minor: 0, jobs: 0, completed: 0, cancelled: 0 };
    point.endDate = date;
    for (const field of ["booked_sales_minor", "collected_revenue_minor", "jobs", "completed", "cancelled"] as const) point[field] += value?.[field] ?? 0;
    grouped.set(key, point);
  }
  return [...grouped.values()];
}
export function chartAxis(maximum: number, counts: boolean) {
  const raw = Math.max(maximum, counts ? 4 : 100) / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = Math.ceil(raw / power) * power;
  const integerStep = counts ? Math.max(1, Math.ceil(step)) : step;
  return { maximum: integerStep * 4, ticks: [0, 1, 2, 3, 4].map(n => n * integerStep) };
}
