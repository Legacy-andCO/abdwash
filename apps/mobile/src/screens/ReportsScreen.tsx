import { staffMoney, t } from "../i18n";
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
  AppButton,
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
import { ReportCharts } from "../components/ReportCharts";
import { FinanceScreen } from "./FinanceScreen";
import { addUaeDays, uaeDateKey, wallDate } from "../time/uaeTime";

export type Period = "today" | "week" | "month" | "custom";
export type ReportsNavigationState = {
  period: Period;
  customStart: string;
  customEnd: string;
};
export function ReportsScreen({
  context,
  navigationState,
  onNavigationStateChange,
  onOpenInventory,
}: {
  context: StaffContext;
  navigationState?: ReportsNavigationState;
  onNavigationStateChange?: (value: ReportsNavigationState) => void;
  onOpenInventory?: () => void;
}) {
  const initial = navigationState ?? {
    period: "week" as const,
    customStart: uaeDateKey(),
    customEnd: uaeDateKey(),
  };
  const [period, setPeriod] = useState<Period>(initial.period);
  const [customStart, setCustomStart] = useState(initial.customStart);
  const [customEnd, setCustomEnd] = useState(initial.customEnd);
  const [financeOpen, setFinanceOpen] = useState(false);
  function updateNavigation(value: Partial<ReportsNavigationState>) {
    const next = { period, customStart, customEnd, ...value };
    if (value.period) setPeriod(value.period);
    if (value.customStart) setCustomStart(value.customStart);
    if (value.customEnd) setCustomEnd(value.customEnd);
    onNavigationStateChange?.(next);
  }
  const range = useMemo(() => {
    const end = uaeDateKey();
    const start = addUaeDays(
      end,
      period === "week" ? -6 : period === "month" ? -29 : 0,
    );
    return period === "custom"
      ? { start: customStart, end: customEnd }
      : { start, end };
  }, [customEnd, customStart, period]);
  const query = useReportQuery(context, range.start, range.end);
  const report = query.data;
  if (financeOpen) {
    return <FinanceScreen context={context} onBack={() => setFinanceOpen(false)} />;
  }
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
        title={t("Reports")}
        subtitle={t("Booked and collected revenue stay distinct")}
      />
      <AppButton title={t("Open Finance")} onPress={() => setFinanceOpen(true)} />
      <AppButton
        title={t("Open Inventory")}
        tone="secondary"
        onPress={() => onOpenInventory?.()}
      />
      <View style={styles.periods}>
        {(["today", "week", "month", "custom"] as const).map((item) => (
          <Pressable
            key={item}
            style={[
              styles.period,
              period === item ? styles.periodActive : undefined,
            ]}
            onPress={() => updateNavigation({ period: item })}
          >
            <Text style={styles.periodText}>{t(item.toUpperCase())}</Text>
          </Pressable>
        ))}
      </View>
      {period === "custom" ? (
        <View style={styles.custom}>
          <DatePickerField
            label={t("From")}
            value={customStart}
            maximumDate={fromIsoDate(customEnd)}
            onChange={(value) => updateNavigation({ customStart: value })}
          />
          <DatePickerField
            label={t("To")}
            value={customEnd}
            minimumDate={fromIsoDate(customStart)}
            maximumDate={wallDate(uaeDateKey())}
            onChange={(value) => updateNavigation({ customEnd: value })}
          />
        </View>
      ) : null}
      {query.isError && report ? (
        <Text style={uiStyles.error}>
          {" " + t("We couldn't refresh reports. Showing the most recent saved data.") + " "}</Text>
      ) : null}
      {query.isPending ? (
        <Skeleton rows={5} />
      ) : !report ? (
        <EmptyState
          title={t("Reports unavailable")}
          body={domainErrorMessage(
            query.error,
            "We couldn't load reports for this period.",
          )}
        />
      ) : (
        <ReportContent report={report} start={range.start} end={range.end} />
      )}
    </ScrollView>
  );
}

function ReportContent({ report, start, end }: { report: ReportV2; start: string; end: string }) {
  const summary = report.summary;
  return (
    <>
      <View style={styles.metrics}>
        <MetricCard
          label={t("Booked sales")}
          value={staffMoney(summary.booked_sales_minor, summary.currency_code)}
        />
        <MetricCard
          label={t("Collected")}
          value={staffMoney(summary.collected_revenue_minor, summary.currency_code)}
        />
        <MetricCard
          label={t("Outstanding")}
          value={staffMoney(summary.outstanding_minor, summary.currency_code)}
        />
        <MetricCard
          label={t("Completed washes")}
          value={String(summary.completed_washes)}
        />
        {report.finance ? (
          <>
            <MetricCard
              label={t("Expenses")}
              value={staffMoney(report.finance.expenses_minor, report.finance.currency_code)}
            />
            <MetricCard
              label={t("Operational profit")}
              value={staffMoney(report.finance.operational_profit_minor, report.finance.currency_code)}
            />
            <MetricCard
              label={t("Margin")}
              value={`${report.finance.margin_percent.toFixed(1)}%`}
            />
          </>
        ) : null}
      </View>
      <ReportCharts report={report} start={start} end={end} />
      <Mix
        title={t("SERVICE MIX")}
        rows={report.service_mix}
        currency={summary.currency_code}
      />
      <Mix
        title={t("PAYMENT MIX")}
        rows={report.payment_mix}
        currency={summary.currency_code}
      />
      <Text style={styles.section}>{t("EMPLOYEE PERFORMANCE")}</Text>
      {report.staff_performance.length ? (
        report.staff_performance.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            <View style={styles.performance}>
              <Value label={t("Hours")} value={item.hours_worked.toFixed(1)} />
              <Value label={t("Completed")} value={String(item.jobs_completed)} />
              <Value label={t("Avg wash")} value={t("{p0} min", { p0: item.average_wash_minutes })} />
              <Value label={t("Late")} value={String(item.late_arrivals)} />
            </View>
            <Text style={uiStyles.muted}>
              {" " + t("Jobs / hour") + " "}{item.jobs_per_worked_hour.toFixed(2)} {" " + t("· handled") + ""}{" "}
              {staffMoney(item.job_value_handled_minor, summary.currency_code)}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No employee performance data")} />
      )}
      <Text style={styles.section}>{t("TEAM PERFORMANCE")}</Text>
      {report.team_performance.length ? (
        report.team_performance.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            <View style={styles.performance}>
              <Value label={t("Completed")} value={String(item.completed_jobs)} />
              <Value label={t("Avg wash")} value={t("{p0} min", { p0: item.average_wash_minutes })} />
              <Value
                label={t("Avg operation")}
                value={t("{p0} min", { p0: item.average_operational_minutes })}
              />
              <Value
                label={t("Jobs / active day")}
                value={item.jobs_per_active_day.toFixed(2)}
              />
            </View>
            <Text style={uiStyles.muted}>
              {" " + t("Value handled ·") + " "}{staffMoney(item.job_value_handled_minor, summary.currency_code)}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No team performance data")} />
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
                <Text style={styles.cardTitle}>{t(item.label)}</Text>
                <Text style={uiStyles.muted}>
                  {item.count} {" " + t("transactions/jobs") + " "}</Text>
              </View>
              <Text style={styles.percent}>{item.percentage.toFixed(1)}%</Text>
            </View>
            <Text style={uiStyles.muted}>
              {staffMoney(item.amount_minor, currency)}
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No {p0} data", { p0: title.toLowerCase() })} />
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
