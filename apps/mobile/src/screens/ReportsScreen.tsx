import { useMemo, useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  Card,
  EmptyState,
  MetricCard,
  ScreenTitle,
  Skeleton,
  uiStyles,
} from "../components/ui";
import { DatePickerField, fromIsoDate } from "../components/pickers";
import { domainErrorMessage } from "../errors/domainErrors";
import type { MixRow, ReportV2, StaffContext } from "../lib";
import { useReportQuery } from "../queries/operations";
import { colors, radii, spacing } from "../theme";

type Period = "today" | "week" | "month" | "custom";
const iso = (value: Date) => value.toISOString().slice(0, 10);

export function ReportsScreen({ context }: { context: StaffContext }) {
  const [period, setPeriod] = useState<Period>("week");
  const [customStart, setCustomStart] = useState(iso(new Date()));
  const [customEnd, setCustomEnd] = useState(iso(new Date()));
  const range = useMemo(() => {
    const end = new Date();
    const start = new Date(end);
    if (period === "week") start.setDate(end.getDate() - 6);
    if (period === "month") start.setDate(end.getDate() - 29);
    return period === "custom"
      ? { start: customStart, end: customEnd }
      : { start: iso(start), end: iso(end) };
  }, [customEnd, customStart, period]);
  const query = useReportQuery(context, range.start, range.end);
  const report = query.data;
  return (
    <ScrollView
      refreshControl={
        <RefreshControl
          refreshing={query.isRefetching}
          onRefresh={() => void query.refetch()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <ScreenTitle
        title="Reports"
        subtitle="Booked and collected revenue stay distinct"
      />
      <View style={styles.periods}>
        {(["today", "week", "month", "custom"] as const).map((item) => (
          <Pressable
            key={item}
            style={[
              styles.period,
              period === item ? styles.periodActive : undefined,
            ]}
            onPress={() => setPeriod(item)}
          >
            <Text style={styles.periodText}>{item.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>
      {period === "custom" ? (
        <View style={styles.custom}>
          <DatePickerField
            label="From"
            value={customStart}
            maximumDate={fromIsoDate(customEnd)}
            onChange={setCustomStart}
          />
          <DatePickerField
            label="To"
            value={customEnd}
            minimumDate={fromIsoDate(customStart)}
            maximumDate={new Date()}
            onChange={setCustomEnd}
          />
        </View>
      ) : null}
      {query.isPending ? (
        <Skeleton rows={5} />
      ) : query.isError || !report ? (
        <EmptyState
          title="Reports unavailable"
          body={domainErrorMessage(
            query.error,
            "We couldn't load reports for this period.",
          )}
        />
      ) : (
        <ReportContent report={report} />
      )}
    </ScrollView>
  );
}

function ReportContent({ report }: { report: ReportV2 }) {
  const summary = report.summary;
  const maximum = Math.max(
    1,
    ...report.series.flatMap((point) => [
      point.booked_sales_minor,
      point.collected_revenue_minor,
    ]),
  );
  return (
    <>
      <View style={styles.metrics}>
        <MetricCard
          label="Booked sales"
          value={`${summary.currency_code} ${(summary.booked_sales_minor / 100).toLocaleString()}`}
        />
        <MetricCard
          label="Collected"
          value={`${summary.currency_code} ${(summary.collected_revenue_minor / 100).toLocaleString()}`}
        />
        <MetricCard
          label="Outstanding"
          value={`${summary.currency_code} ${(summary.outstanding_minor / 100).toLocaleString()}`}
        />
        <MetricCard
          label="Completed washes"
          value={String(summary.completed_washes)}
        />
      </View>
      <Card>
        <Text style={styles.cardTitle}>Revenue and jobs</Text>
        <Text style={uiStyles.muted}>
          Booked / collected · jobs, completed, cancelled
        </Text>
        {report.series.length ? (
          report.series.map((point) => (
            <View key={point.date} style={styles.graphRow}>
              <Text style={styles.graphLabel}>{point.date.slice(5)}</Text>
              <View style={styles.graphTracks}>
                <View style={styles.track}>
                  <View
                    style={[
                      styles.bar,
                      {
                        width: `${Math.max(3, (point.booked_sales_minor / maximum) * 100)}%`,
                      },
                    ]}
                  />
                </View>
                <View style={styles.track}>
                  <View
                    style={[
                      styles.collectedBar,
                      {
                        width: `${Math.max(3, (point.collected_revenue_minor / maximum) * 100)}%`,
                      },
                    ]}
                  />
                </View>
              </View>
              <Text style={styles.graphValue}>
                {(point.booked_sales_minor / 100).toFixed(0)}/
                {(point.collected_revenue_minor / 100).toFixed(0)} ·{" "}
                {point.jobs}/{point.completed}/{point.cancelled}
              </Text>
            </View>
          ))
        ) : (
          <EmptyState title="No report data for this period" />
        )}
      </Card>
      <Mix
        title="SERVICE MIX"
        rows={report.service_mix}
        currency={summary.currency_code}
      />
      <Mix
        title="PAYMENT MIX"
        rows={report.payment_mix}
        currency={summary.currency_code}
      />
      <Text style={styles.section}>EMPLOYEE PERFORMANCE</Text>
      {report.staff_performance.length ? (
        report.staff_performance.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            <View style={styles.performance}>
              <Value label="Hours" value={item.hours_worked.toFixed(1)} />
              <Value label="Completed" value={String(item.jobs_completed)} />
              <Value label="Avg wash" value={`${item.average_wash_minutes}m`} />
              <Value label="Late" value={String(item.late_arrivals)} />
            </View>
            <Text style={uiStyles.muted}>
              Jobs / hour {item.jobs_per_worked_hour.toFixed(2)} · handled{" "}
              {summary.currency_code}{" "}
              {(item.job_value_handled_minor / 100).toLocaleString()}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No employee performance data" />
      )}
      <Text style={styles.section}>TEAM PERFORMANCE</Text>
      {report.team_performance.length ? (
        report.team_performance.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            <View style={styles.performance}>
              <Value label="Completed" value={String(item.completed_jobs)} />
              <Value label="Avg wash" value={`${item.average_wash_minutes}m`} />
              <Value
                label="Avg operation"
                value={`${item.average_operational_minutes}m`}
              />
              <Value
                label="Jobs / active day"
                value={item.jobs_per_active_day.toFixed(2)}
              />
            </View>
            <Text style={uiStyles.muted}>
              Value handled · {summary.currency_code}{" "}
              {(item.job_value_handled_minor / 100).toLocaleString()}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No team performance data" />
      )}
    </>
  );
}
function Mix({
  title,
  rows,
  currency,
}: {
  title: string;
  rows: MixRow[];
  currency: string;
}) {
  return (
    <>
      <Text style={styles.section}>{title}</Text>
      {rows.length ? (
        rows.map((item) => (
          <Card key={item.key}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>{item.label}</Text>
                <Text style={uiStyles.muted}>
                  {item.count} transactions/jobs
                </Text>
              </View>
              <Text style={styles.percent}>{item.percentage.toFixed(1)}%</Text>
            </View>
            <Text style={uiStyles.muted}>
              {currency} {(item.amount_minor / 100).toLocaleString()}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title={`No ${title.toLowerCase()} data`} />
      )}
    </>
  );
}
function Value({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.value}>
      <Text style={styles.valueNumber}>{value}</Text>
      <Text style={styles.valueLabel}>{label}</Text>
    </View>
  );
}
const styles = StyleSheet.create({
  periods: {
    flexDirection: "row",
    gap: 3,
    backgroundColor: colors.secondary,
    padding: 3,
    borderRadius: radii.sm,
  },
  period: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderRadius: 8,
  },
  periodActive: { backgroundColor: colors.surface },
  periodText: { color: colors.text, fontSize: 10, fontWeight: "900" },
  custom: { gap: spacing.sm },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  cardTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  graphRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  graphLabel: { width: 40, color: colors.textSecondary, fontSize: 11 },
  graphTracks: { flex: 1, gap: 3 },
  track: {
    height: 8,
    borderRadius: radii.pill,
    backgroundColor: colors.secondary,
    overflow: "hidden",
  },
  bar: {
    height: "100%",
    backgroundColor: colors.primary,
    borderRadius: radii.pill,
  },
  collectedBar: {
    height: "100%",
    backgroundColor: colors.success,
    borderRadius: radii.pill,
  },
  graphValue: {
    width: 124,
    textAlign: "right",
    color: colors.text,
    fontWeight: "800",
    fontSize: 10,
  },
  section: {
    color: colors.textSecondary,
    fontWeight: "900",
    fontSize: 11,
    letterSpacing: 1.2,
    marginTop: spacing.md,
  },
  performance: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  value: {
    width: "47%",
    backgroundColor: colors.surfaceElevated,
    padding: spacing.md,
    borderRadius: radii.md,
  },
  valueNumber: { color: colors.text, fontSize: 20, fontWeight: "900" },
  valueLabel: { color: colors.textSecondary, fontSize: 11 },
  percent: { color: colors.primary, fontSize: 20, fontWeight: "900" },
});
