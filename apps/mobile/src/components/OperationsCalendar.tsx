import { useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { calendarDays, jobsByDate, monthWindow, shiftMonth } from "../calendar/calendarState";
import { useJobCalendarQuery } from "../queries/operations";
import type { CalendarJob, StaffContext } from "../lib";
import { colors, radii, spacing } from "../theme";
import { AppButton, EmptyState, Skeleton, StatusChip, uiStyles } from "./ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { formatUaeTime, uaeDateKey } from "../time/uaeTime";

export function OperationsCalendar({
  context,
  onOpenJob,
}: {
  context: StaffContext;
  onOpenJob: (jobId: string) => void;
}) {
  const today = uaeDateKey();
  const [month, setMonth] = useState(() => today.slice(0, 7));
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const range = useMemo(() => monthWindow(month), [month]);
  const query = useJobCalendarQuery(context, range.start, range.end);
  const jobs = query.data?.jobs ?? [];
  const grouped = useMemo(() => jobsByDate(jobs), [jobs]);
  const days = useMemo(
    () => calendarDays(range.start, range.end),
    [range.end, range.start],
  );
  const agenda = selectedDate ? grouped.get(selectedDate) ?? [] : [];
  const monthLabel = new Date(`${month}-01T00:00:00Z`).toLocaleDateString([], {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <View>
      <View style={styles.toolbar}>
        <Pressable accessibilityLabel="Previous month" onPress={() => setMonth(shiftMonth(month, -1))}>
          <Text style={uiStyles.link}>←</Text>
        </Pressable>
        <View style={styles.monthTitle}>
          <Text style={styles.heading}>{monthLabel}</Text>
          <Pressable onPress={() => setMonth(today.slice(0, 7))}>
            <Text style={uiStyles.link}>Today</Text>
          </Pressable>
        </View>
        <Pressable accessibilityLabel="Next month" onPress={() => setMonth(shiftMonth(month, 1))}>
          <Text style={uiStyles.link}>→</Text>
        </Pressable>
      </View>
      {query.isError && jobs.length ? (
        <Text style={styles.warning}>Offline · showing the last saved calendar</Text>
      ) : null}
      {query.isPending && !jobs.length ? (
        <Skeleton rows={5} />
      ) : query.isError && !jobs.length ? (
        <EmptyState
          title="Calendar unavailable"
          body={domainErrorMessage(query.error, "We couldn't load this month.")}
          action={<AppButton title="Try again" onPress={() => void query.refetch()} />}
        />
      ) : (
        <>
          <View style={styles.weekRow}>
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
              <Text key={day} style={styles.weekday}>{day}</Text>
            ))}
          </View>
          <View style={styles.grid}>
            {days.map((day) => {
              const dayJobs = grouped.get(day) ?? [];
              const inMonth = day.slice(0, 7) === month;
              return (
                <Pressable
                  key={day}
                  accessibilityRole="button"
                  accessibilityLabel={`${day}, ${dayJobs.length} jobs`}
                  style={[
                    styles.day,
                    day === today ? styles.today : undefined,
                    day === selectedDate ? styles.selected : undefined,
                  ]}
                  onPress={() => setSelectedDate(day)}
                >
                  <Text style={[styles.dayNumber, !inMonth ? styles.outside : undefined]}>
                    {Number(day.slice(-2))}
                  </Text>
                  {dayJobs.slice(0, 3).map((job) => (
                    <View
                      key={job.job_id}
                      style={[
                        styles.event,
                        job.status === "en_route" ? styles.enRoute : undefined,
                        job.status === "arrived" ? styles.arrived : undefined,
                        job.status === "in_progress" ? styles.inProgress : undefined,
                        job.status === "completed" ? styles.completed : undefined,
                        job.team_id ? undefined : styles.unassigned,
                      ]}
                    >
                      <Text numberOfLines={1} style={styles.eventText}>
                        {job.team_short_name ?? "UN"} · {job.vehicle_label}
                      </Text>
                      <Text style={styles.eventTime}>{formatUaeTime(job.scheduled_start)}</Text>
                    </View>
                  ))}
                  {dayJobs.length > 3 ? (
                    <Text style={styles.more}>+{dayJobs.length - 3} more</Text>
                  ) : null}
                </Pressable>
              );
            })}
          </View>
        </>
      )}
      <Modal
        visible={selectedDate !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedDate(null)}
      >
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <View style={uiStyles.row}>
              <Text style={styles.heading}>{selectedDate}</Text>
              <Pressable onPress={() => setSelectedDate(null)}><Text style={uiStyles.link}>Close</Text></Pressable>
            </View>
            <ScrollView>
              {agenda.length ? agenda.map((job) => (
                <AgendaRow key={job.job_id} job={job} onPress={() => {
                  setSelectedDate(null);
                  onOpenJob(job.job_id);
                }} />
              )) : <Text style={uiStyles.muted}>No scheduled jobs.</Text>}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function AgendaRow({ job, onPress }: { job: CalendarJob; onPress: () => void }) {
  return (
    <Pressable style={styles.agendaRow} onPress={onPress}>
      <View style={uiStyles.row}>
        <Text style={styles.heading}>{formatUaeTime(job.scheduled_start)}</Text>
        <StatusChip value={job.status} />
      </View>
      <Text style={uiStyles.body}>{job.vehicle_label} · {job.service_label}</Text>
      <Text style={uiStyles.muted}>{job.team_short_name ?? "Unassigned"}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  toolbar: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md },
  monthTitle: { alignItems: "center", gap: spacing.xs },
  heading: { color: colors.text, fontSize: 16, fontWeight: "800" },
  warning: { color: colors.warning, marginBottom: spacing.sm },
  weekRow: { flexDirection: "row" },
  weekday: { width: "14.285%", textAlign: "center", color: colors.textSecondary, fontSize: 11, fontWeight: "700", paddingBottom: spacing.xs },
  grid: { flexDirection: "row", flexWrap: "wrap", borderTopWidth: 1, borderLeftWidth: 1, borderColor: colors.border },
  day: { width: "14.285%", minHeight: 102, borderRightWidth: 1, borderBottomWidth: 1, borderColor: colors.border, padding: 3, backgroundColor: colors.surface },
  today: { borderTopWidth: 3, borderTopColor: colors.primary },
  selected: { backgroundColor: colors.background },
  dayNumber: { color: colors.text, fontSize: 12, fontWeight: "700" },
  outside: { color: colors.textSecondary },
  event: { backgroundColor: colors.background, borderLeftWidth: 2, borderLeftColor: colors.primary, borderRadius: 3, padding: 2, marginTop: 3 },
  unassigned: { borderLeftColor: colors.warning },
  enRoute: { borderLeftColor: colors.accent },
  arrived: { backgroundColor: colors.warningSurface, borderLeftColor: colors.warning },
  inProgress: { backgroundColor: colors.secondary, borderLeftColor: colors.primary },
  completed: { backgroundColor: colors.successSurface, borderLeftColor: colors.success },
  eventText: { color: colors.text, fontSize: 8, fontWeight: "700" },
  eventTime: { color: colors.textSecondary, fontSize: 8 },
  more: { color: colors.primary, fontSize: 8, fontWeight: "700", marginTop: 2 },
  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(15,15,16,0.45)" },
  sheet: { maxHeight: "75%", backgroundColor: colors.surface, padding: spacing.lg, borderTopLeftRadius: radii.lg, borderTopRightRadius: radii.lg, gap: spacing.md },
  agendaRow: { paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border, gap: spacing.xs },
});
