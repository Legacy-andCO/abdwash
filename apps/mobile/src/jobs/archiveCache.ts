import type { QueryClient } from "@tanstack/react-query";
import type { CalendarJob, Dashboard, Job } from "../lib";

export async function removeArchivedBookingFromCaches(
  client: QueryClient, scope: string, job: Job,
) {
  // Cancel older fetches first so they cannot put the archived job back.
  const prefixes = ["jobs", "calendar", "dashboard"];
  await Promise.all(prefixes.map((prefix) => client.cancelQueries({ queryKey: [prefix, scope] })));
  client.setQueriesData<{ jobs: Job[]; next_offset: number | null }>(
    { queryKey: ["jobs", scope] },
    (data) => data ? { ...data, jobs: data.jobs.filter((item) => item.booking_id !== job.booking_id) } : data,
  );
  client.setQueriesData<{ jobs: CalendarJob[] }>(
    { queryKey: ["calendar", scope] },
    (data) => data ? { ...data, jobs: data.jobs.filter((item) => item.job_id !== job.id) } : data,
  );
  client.setQueriesData<Dashboard>(
    { queryKey: ["dashboard", scope] },
    (data) => data ? { ...data, active_jobs: data.active_jobs.filter((item) => item.booking_id !== job.booking_id) } : data,
  );
  for (const prefix of prefixes) void client.invalidateQueries({ queryKey: [prefix, scope] });
}
