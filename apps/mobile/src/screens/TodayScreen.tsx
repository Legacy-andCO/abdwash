import { useEffect, useState } from "react";
import {
  Alert,
  RefreshControl,
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
  onOpenInventory,
  onOpenServices,
}: {
  context: StaffContext;
  onOpenCustomers?: () => void;
  onOpenInventory?: () => void;
  onOpenServices?: () => void;
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
  const jobItems = jobs.data?.jobs ?? [];
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
        "Attendance not changed",
        domainErrorMessage(reason, "The server did not confirm attendance."),
      );
    }
  }
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
        eyebrow={formatUaeDate(new Date(), undefined, {
            weekday: "long",
            day: "numeric",
            month: "long",
          })
          .toUpperCase()}
        title={`Good ${greeting()}, ${firstName(context.display_name)}`}
        subtitle={
          management
            ? "Live business operations"
            : "Everything you need for today's work"
        }
      />
      <AppButton
        title="Open Inventory"
        tone="secondary"
        onPress={() => onOpenInventory?.()}
      />
      {management ? (
        <AppButton
          title="Services & pricing"
          tone="secondary"
          onPress={() => onOpenServices?.()}
        />
      ) : null}
      {personalCash.data ? (
        <Card>
          <Text style={styles.kicker}>MY CASH</Text>
          <View style={styles.cashMetrics}>
            <MetricCard
              label="Collected today"
              value={`${personalCash.data.currency_code} ${(
                personalCash.data.collected_today_minor / 100
              ).toLocaleString()}`}
            />
            <MetricCard
              label="Awaiting handover"
              value={`${personalCash.data.currency_code} ${(
                personalCash.data.awaiting_handover_minor / 100
              ).toLocaleString()}`}
            />
          </View>
        </Card>
      ) : null}
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
          onOpenCustomers={onOpenCustomers}
        />
      ) : (
        <>
          <Card>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.kicker}>ATTENDANCE</Text>
                <Text style={styles.cardTitle}>
                  {ownAttendance?.clock_in_at && !ownAttendance.clock_out_at
                    ? "You're clocked in"
                    : ownAttendance?.status === "approved_leave"
                      ? "Approved leave"
                      : "Ready to start?"}
                </Text>
              </View>
              {ownAttendance ? (
                <StatusChip value={ownAttendance.status} />
              ) : null}
            </View>
            {ownShift ? (
              <Text style={uiStyles.muted}>
                Today's shift · {ownShift.start_time.slice(0, 5)}–
                {ownShift.end_time.slice(0, 5)}
                {ownShift.team_name ? ` · ${ownShift.team_name}` : ""}
              </Text>
            ) : (
              <Text style={uiStyles.muted}>No shift assigned today</Text>
            )}
            {ownAttendance?.clock_in_at && !ownAttendance.clock_out_at ? (
              <Text style={styles.time}>
                Started{" "}
                {new Date(ownAttendance.clock_in_at).toLocaleTimeString([], {
                  hour: "numeric",
                  minute: "2-digit",
                })}{" "}
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
                  ? "Saving…"
                  : ownAttendance?.clock_in_at && !ownAttendance.clock_out_at
                    ? "Clock out"
                    : "Clock in"
              }
              disabled={
                clock.isPending || ownAttendance?.status === "approved_leave"
              }
              loading={clock.isPending}
              onPress={() => void toggleClock()}
            />
          </Card>
          {next ? (
            <Card>
              <Text style={styles.kicker}>
                {active ? "ACTIVE NOW" : "NEXT JOB"}
              </Text>
              <Text style={styles.nextTime}>
                {formatUaeTime(next.scheduled_start)}
              </Text>
              <Text style={styles.cardTitle}>
                {next.vehicles[0]
                  ? `${next.vehicles[0].make} ${next.vehicles[0].model}`
                  : next.customer_name}
              </Text>
              <Text style={uiStyles.body}>
                {next.vehicles[0]?.service_name}
              </Text>
              <Text style={uiStyles.muted}>{next.written_address}</Text>
              <StatusChip value={next.status} />
            </Card>
          ) : (
            <EmptyState
              title="No jobs today"
              body="Your next assigned or team job will appear here."
            />
          )}
          {jobItems
            .filter(
              (job) =>
                job.id !== next?.id &&
                !["completed", "cancelled"].includes(job.status),
            )
            .map((job) => (
              <Card key={job.id}>
                <View style={uiStyles.row}>
                  <Text style={styles.cardTitle}>
                    {formatUaeTime(job.scheduled_start)}
                  </Text>
                  <StatusChip value={job.status} />
                </View>
                <Text style={uiStyles.muted}>
                  {job.customer_name} · {job.vehicles[0]?.service_name}
                </Text>
              </Card>
            ))}
        </>
      )}
    </ScrollView>
  );
}

function ManagerDashboard({
  value,
  attendance,
  onOpenCustomers,
}: {
  value: Dashboard | null;
  attendance: AttendanceOverview[];
  onOpenCustomers?: () => void;
}) {
  if (!value) return <EmptyState title="Dashboard unavailable" />;
  return (
    <>
      {onOpenCustomers ? (
        <Card>
          <Text style={styles.kicker}>CUSTOMER MANAGEMENT</Text>
          <Text style={styles.cardTitle}>Customers</Text>
          <Text style={uiStyles.muted}>
            Search profiles, saved details, booking history and loyalty.
          </Text>
          <AppButton title="Open customers" onPress={onOpenCustomers} />
        </Card>
      ) : null}
      <View style={styles.metrics}>
        {value.metrics.slice(0, 4).map((metric) => (
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
      <Text style={styles.section}>NEEDS ATTENTION</Text>
      {value.attention.length ? (
        value.attention.map((item) => (
          <Card key={item.kind}>
            <View style={uiStyles.row}>
              <Text style={styles.cardTitle}>{item.count}</Text>
              <Text style={[uiStyles.body, styles.flex]}>{item.label}</Text>
            </View>
          </Card>
        ))
      ) : (
        <EmptyState
          title="Everything is under control"
          body="No operational items need attention."
        />
      )}
      <Text style={styles.section}>ACTIVE NOW</Text>
      {value.active_jobs.length ? (
        value.active_jobs.map((job: Job) => (
          <Card key={job.id}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>
                  {job.assigned_team_name ??
                    job.assigned_staff_name ??
                    "Unassigned"}
                </Text>
                <Text style={uiStyles.muted}>
                  {job.vehicles[0]
                    ? `${job.vehicles[0].make} ${job.vehicles[0].model}`
                    : job.booking_reference}
                </Text>
              </View>
              <StatusChip value={job.status} />
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title="No active jobs" />
      )}
      <Text style={styles.section}>TEAM</Text>
      {attendance.length ? (
        attendance.map((item) => (
          <Card key={item.staff_id}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>{item.staff_name}</Text>
                <Text style={uiStyles.muted}>
                  {item.shift_name ?? "No shift today"}
                  {item.late_minutes ? ` · ${item.late_minutes} min late` : ""}
                </Text>
              </View>
              <StatusChip value={item.status} />
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title="No active staff" />
      )}
    </>
  );
}
const greeting = () => {
  const hour = new Date().getHours();
  return hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
};
const firstName = (name: string) => name.trim().split(/\s+/)[0] || "team";
const formatMinutes = (value: number) =>
  `${String(Math.floor(value / 60)).padStart(2, "0")}h ${String(Math.max(0, value) % 60).padStart(2, "0")}m`;
const styles = StyleSheet.create({
  kicker: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
  },
  cardTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  time: { color: colors.text, fontSize: 16, fontWeight: "800" },
  nextTime: { color: colors.text, fontSize: 30, fontWeight: "900" },
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
