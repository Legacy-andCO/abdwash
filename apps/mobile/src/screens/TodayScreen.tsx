import { t } from "../i18n";
import { Alert } from "../alert";
import { useEffect, useState } from "react";
import {
  RefreshControl,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { capabilities } from "../capabilities";
import {
  AppButton,
  Card,
  EmptyState,
  Disclosure,
  MetricCard,
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { successHaptic } from "../haptics";
import type { AttendanceOverview, Dashboard, Job, StaffContext } from "../lib";
import {
  useAttendanceOverviewQuery,
  useClockMutation,
  useDashboardQuery,
  useJobsQuery,
  usePersonalCashQuery,
  useShiftAssignmentsQuery,
} from "../queries/operations";
import { colors, spacing } from "../theme";
import { formatUaeDate, formatUaeTime, uaeDateKey } from "../time/uaeTime";

const today = uaeDateKey;

export function TodayScreen({
  context,
  onOpenCustomers,
  onOpenComplaints,
  onOpenInventory,
  onOpenServices,
  onBook,
  onOpenJob,
  onOpenJobs,
  onOpenTeam,
}: {
  context: StaffContext;
  onOpenCustomers?: () => void;
  onOpenComplaints?: () => void;
  onOpenInventory?: () => void;
  onOpenServices?: () => void;
  onBook?: () => void;
  onOpenJob?: (id: string) => void;
  onOpenJobs?: (view?: import("./JobsScreen").JobView) => void;
  onOpenTeam?: (section?: import("./TeamScreen").TeamSection) => void;
}) {
  const management = capabilities(context.role).canViewAllJobs;
  const dashboard = useDashboardQuery(context, today(), management);
  const jobs = useJobsQuery(context, {
    view: "today",
    scope: management ? "all" : "my",
    date: today(),
    limit: 50,
  }, !management);
  const attendance = useAttendanceOverviewQuery(context);
  const shifts = useShiftAssignmentsQuery(context, undefined, undefined, !management);
  const clock = useClockMutation(context);
  const personalCash = usePersonalCashQuery(context, today());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);
  const ownAttendance = attendance.data?.find(
    (item) => item.staff_id === context.staff_id,
  );
  const ownShift = shifts.data?.find(
    (item) => item.staff_id === context.staff_id,
  );
  const jobItems = [...(jobs.data?.jobs ?? [])].sort((a, b) => Date.parse(a.scheduled_start) - Date.parse(b.scheduled_start));
  const active = jobItems.find((job) =>
    ["en_route", "arrived", "in_progress"].includes(job.status),
  );
  const next =
    active ??
    jobItems.find((job) => !["completed", "cancelled"].includes(job.status));
  const loading = management
    ? dashboard.isPending || attendance.isPending
    : jobs.isPending || attendance.isPending || shifts.isPending;
  const refreshing = management
    ? dashboard.isRefetching || attendance.isRefetching || personalCash.isRefetching
    :
        jobs.isRefetching ||
        attendance.isRefetching ||
        shifts.isRefetching ||
        personalCash.isRefetching;
  const error = management
    ? (dashboard.error ?? attendance.error)
    : (jobs.error ?? attendance.error ?? shifts.error);
  async function refresh() {
    await Promise.all(
      management
        ? [dashboard.refetch(), attendance.refetch(), personalCash.refetch()]
        : [
            jobs.refetch(),
            attendance.refetch(),
            shifts.refetch(),
            personalCash.refetch(),
          ],
    );
  }
  async function toggleClock() {
    try {
      await clock.mutateAsync(
        ownAttendance?.clock_in_at && !ownAttendance.clock_out_at
          ? "clock-out"
          : "clock-in",
      );
      await successHaptic();
    } catch (reason) {
      Alert.alert(
        t("Attendance not changed"),
        domainErrorMessage(reason, "The server did not confirm attendance."),
      );
    }
  }
  const attendanceNeedsAction = !attendance.isPending && !attendance.error && !ownAttendance?.clock_in_at && ownAttendance?.status !== "approved_leave";
  const attendanceSection = (
    <Disclosure title={t("Attendance & shift")} initiallyOpen={attendanceNeedsAction}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.kicker}>{t("ATTENDANCE")}</Text>
                <Text style={styles.cardTitle}>
                  {ownAttendance?.clock_in_at && !ownAttendance.clock_out_at
                    ? t("You're clocked in")
                    : ownAttendance?.status === "approved_leave"
                      ? t("Approved leave")
                      : t("Ready to start?")}
                </Text>
              </View>
              {ownAttendance ? (
                <StatusChip value={ownAttendance.status} />
              ) : null}
            </View>
            {ownShift ? (
              <Text style={uiStyles.muted}>
                {" " + t("Today's shift ·") + " "}{ownShift.start_time.slice(0, 5)}–
                {ownShift.end_time.slice(0, 5)}
                {ownShift.team_name ? t(" · {p0}", { p0: ownShift.team_name }) : ""}
              </Text>
            ) : (
              <Text style={uiStyles.muted}>{t("No shift assigned today")}</Text>
            )}
            {ownAttendance?.clock_in_at && !ownAttendance.clock_out_at ? (
              <Text style={styles.time}>
                {" " + t("Started") + ""}{" "}
                {formatUaeTime(ownAttendance.clock_in_at)}{" "}
                ·{" "}
                {formatMinutes(
                  Math.floor(
                    (now - Date.parse(ownAttendance.clock_in_at)) / 60_000,
                  ),
                )}
              </Text>
            ) : null}
            <AppButton
              title={
                clock.isPending
                  ? t("Saving…")
                  : ownAttendance?.clock_in_at && !ownAttendance.clock_out_at
                    ? t("Clock out")
                    : t("Clock in")
              }
              disabled={
                clock.isPending || ownAttendance?.status === "approved_leave"
              }
              loading={clock.isPending}
              tone="secondary"
              onPress={() => void toggleClock()}
            />
          </Disclosure>
  );
  return (
    <ScrollView
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void refresh()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <ScreenTitle
        subtitle={formatUaeDate(new Date(), undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
          })
          + " · " + t("Abu Dhabi time")}
        title={t("Today")}
      />
      <View style={styles.actions}>
        <View style={styles.action}><AppButton title={t("Book a wash")} onPress={() => onBook?.()} /></View>
        <View style={styles.action}><AppButton title={t("View schedule")} tone="secondary" onPress={() => onOpenJobs?.("today")} /></View>
      </View>
      {error ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(
            error,
            "We couldn't refresh operations. Pull down to retry.",
          )}
        </Text>
      ) : null}
      {loading ? (
        <Skeleton rows={4} />
      ) : management ? (
        <ManagerDashboard
          value={dashboard.data ?? null}
          attendance={attendance.data ?? []}
          onOpenJob={onOpenJob}
          onOpenJobs={onOpenJobs}
          onOpenTeam={onOpenTeam}
        />
      ) : (
        <>

          {attendanceNeedsAction ? attendanceSection : null}
          {next ? (
            <Pressable accessibilityRole="button" accessibilityLabel={t("Open job {p0}, {p1}", { p0: next.booking_reference, p1: next.customer_name })} onPress={() => onOpenJob?.(next.id)}><Card>
              <Text style={styles.kicker}>
                {active ? t("ACTIVE NOW") : t("NEXT JOB")}
              </Text>
              <Text style={styles.nextTime}>
                {formatUaeTime(next.scheduled_start)}
              </Text>
              <Text style={styles.cardTitle}>
                {next.customer_name}
              </Text>
              <Text style={uiStyles.body}>
                {next.vehicles[0] ? t("{p0} {p1} · {p2}", { p0: next.vehicles[0].make, p1: next.vehicles[0].model, p2: next.vehicles[0].service_name }) : next.booking_reference}
              </Text>
              <Text style={uiStyles.muted}>{next.written_address}</Text>
              <StatusChip value={next.status} />
              <Text style={styles.link}>{t("View job details")}</Text>
            </Card></Pressable>
          ) : (
            <EmptyState
              title={t("No jobs today")}
              body={t("Assigned jobs will appear here. Use Book a wash to create a new appointment.")}
            />
          )}
          {jobItems
            .filter(
              (job) =>
                job.id !== next?.id &&
                !["completed", "cancelled"].includes(job.status),
            )
            .map((job) => (
              <Pressable key={job.id} accessibilityRole="button" accessibilityLabel={t("Open job {p0}, {p1}", { p0: job.booking_reference, p1: job.customer_name })} onPress={() => onOpenJob?.(job.id)}><Card>
                <View style={uiStyles.row}>
                  <Text style={styles.cardTitle}>
                    {formatUaeTime(job.scheduled_start)}
                  </Text>
                  <StatusChip value={job.status} />
                </View>
                <Text style={uiStyles.muted}>
                  {job.customer_name} · {job.vehicles[0]?.service_name}
                </Text>
                <Text style={styles.link}>{t("View job details")}</Text>
              </Card></Pressable>
            ))}
          {!attendanceNeedsAction ? attendanceSection : null}
        </>
      )}
      {management ? (
        <Disclosure title={t("Customers & management tools")}>
        <Text style={uiStyles.muted}>{t("Customer follow-ups, stock and business settings.")}</Text>
        <AppButton title={t("Customers")} tone="secondary" onPress={() => onOpenCustomers?.()} />
        <AppButton title={t("Customer complaints")} tone="secondary" onPress={() => onOpenComplaints?.()} />
        <AppButton title={t("Inventory")} tone="secondary" onPress={() => onOpenInventory?.()} />
        <AppButton title={t("Services & pricing")} tone="secondary" onPress={() => onOpenServices?.()} />
        <Text style={uiStyles.muted}>{t("Financial reports and cash handovers are in Reports → Open Finance.")}</Text>
        </Disclosure>
      ) : null}
      <Disclosure title={management ? t("My cash") : t("My cash & inventory")}>
        {personalCash.data ? <View style={styles.cashMetrics}>
          <MetricCard label={t("Collected today")} value={`${personalCash.data.currency_code} ${(personalCash.data.collected_today_minor / 100).toLocaleString()}`} />
          <MetricCard label={t("Awaiting handover")} value={`${personalCash.data.currency_code} ${(personalCash.data.awaiting_handover_minor / 100).toLocaleString()}`} />
        </View> : <Text style={uiStyles.muted}>{personalCash.isPending ? t("Loading cash summary…") : t("Cash summary couldn't load. Pull down to retry.")}</Text>}
        {!management ? <AppButton title={t("Open Inventory")} tone="secondary" onPress={() => onOpenInventory?.()} /> : null}
      </Disclosure>
    </ScrollView>
  );
}

function ManagerDashboard({
  value,
  attendance,
  onOpenJob,
  onOpenJobs,
  onOpenTeam,
}: {
  value: Dashboard | null;
  attendance: AttendanceOverview[];
  onOpenJob?: (id: string) => void;
  onOpenJobs?: (view?: import("./JobsScreen").JobView) => void;
  onOpenTeam?: (section?: import("./TeamScreen").TeamSection) => void;
}) {
  if (!value) return <EmptyState title={t("Dashboard unavailable")} />;
  return (
    <>
      <View style={styles.metrics}>
        {[...value.metrics].sort((a, b) => Number(["booked", "collected"].includes(a.key)) - Number(["booked", "collected"].includes(b.key))).slice(0, 4).map((metric) => (
          <MetricCard
            key={metric.key}
            label={metric.label}
            value={
              metric.key === "booked" || metric.key === "collected"
                ? `${value.currency_code} ${(metric.value / 100).toLocaleString()}`
                : String(metric.value)
            }
          />
        ))}
      </View>
      <Text style={styles.section}>{t("NEEDS ATTENTION")}</Text>
      {value.attention.length ? (
        value.attention.map((item) => (
          <Card key={item.kind}>
            <View style={uiStyles.row}>
              <Text style={styles.cardTitle}>{item.count}</Text>
              <Text style={[uiStyles.body, styles.flex]}>{item.label}</Text>
            </View>
            <AppButton title={t("Review outstanding work")} tone="secondary" onPress={() =>
              ["leave_requests", "cancellations", "late_staff", "missed_shifts"].includes(item.kind)
                ? onOpenTeam?.("attendance")
                : onOpenJobs?.(item.kind.includes("unassigned") ? "unassigned" : item.kind.includes("reschedul") ? "rescheduling" : "today")} />
          </Card>
        ))
      ) : (
        <EmptyState
          title={t("Everything is under control")}
          body={t("No operational items need attention.")}
        />
      )}
      <Text style={styles.section}>{t("ACTIVE NOW")}</Text>
      {value.active_jobs.length ? (
        value.active_jobs.map((job: Job) => (
          <Pressable key={job.id} accessibilityRole="button" accessibilityLabel={t("Open job {p0}, {p1}", { p0: job.booking_reference, p1: job.customer_name })} onPress={() => onOpenJob?.(job.id)}><Card>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>
                  {job.assigned_team_name ??
                    job.assigned_staff_name ??
                    t("Unassigned")}
                </Text>
                <Text style={uiStyles.muted}>
                  {job.vehicles[0]
                    ? t("{p0} {p1}", { p0: job.vehicles[0].make, p1: job.vehicles[0].model })
                    : job.booking_reference}
                </Text>
              </View>
              <StatusChip value={job.status} />
            </View>
            <Text style={uiStyles.body}>{job.customer_name} · {formatUaeTime(job.scheduled_start)}</Text>
            <Text style={styles.link}>{t("View job details")}</Text>
          </Card></Pressable>
        ))
      ) : (
        <EmptyState title={t("No active jobs")} />
      )}
      <Disclosure title={t("Team attendance · {p0} clocked in", { p0: attendance.filter(item => item.clock_in_at && !item.clock_out_at).length })}>
      {attendance.length ? (
        attendance.map((item) => (
          <Card key={item.staff_id}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>{item.staff_name}</Text>
                <Text style={uiStyles.muted}>
                  {item.shift_name ?? t("No shift today")}
                  {item.late_minutes ? t(" · {p0} min late", { p0: item.late_minutes }) : ""}
                </Text>
              </View>
              <StatusChip value={item.status} />
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No active staff")} />
      )}
      <AppButton title={t("View teams")} tone="secondary" onPress={() => onOpenTeam?.()} />
      </Disclosure>
    </>
  );
}
const formatMinutes = (value: number) =>
  `${String(Math.floor(value / 60)).padStart(2, "0")}h ${String(Math.max(0, value) % 60).padStart(2, "0")}m`;
const styles = StyleSheet.create({
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  action: { flex: 1, minWidth: 140 },
  link: { color: colors.primaryPressed, fontSize: 14, fontWeight: "600" },
  kicker: {
    color: colors.primaryPressed,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
  cardTitle: { color: colors.text, fontSize: 18, fontWeight: "700" },
  time: { color: colors.text, fontSize: 16, fontWeight: "800" },
  nextTime: { color: colors.text, fontSize: 28, fontWeight: "700" },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  cashMetrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  section: {
    color: colors.textSecondary,
    fontWeight: "900",
    fontSize: 12,
    letterSpacing: 1.2,
    marginTop: spacing.md,
  },
  flex: { flex: 1 },
});
