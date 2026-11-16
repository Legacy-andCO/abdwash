import { staffLocale, t } from "../i18n";
import { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import Svg, { Line, Rect, Text as SvgText } from "react-native-svg";
import type { ReportV2 } from "../lib";
import { chartAxis, reportChartData, type ChartPoint } from "../reports/chartData";
import { colors, spacing } from "../theme";
import { Card, Disclosure, uiStyles } from "./ui";

type Series = { field: "booked_sales_minor" | "collected_revenue_minor" | "jobs" | "completed" | "cancelled"; label: string; color: string };
export function ReportCharts({ report, start, end }: { report: ReportV2; start: string; end: string }) {
  const points = useMemo(() => reportChartData(report.series, start, end), [report.series, start, end]);
  return <>
    <Chart title={t("Revenue")} subtitle={t("Booked revenue versus collected revenue")} currency={report.summary.currency_code} points={points}
      series={[{ field: "booked_sales_minor", label: t("Booked revenue"), color: colors.primaryPressed }, { field: "collected_revenue_minor", label: t("Collected revenue"), color: colors.success }]} />
    <Chart title={t("Job Activity")} subtitle={t("Bookings grouped by scheduled appointment date")} points={points}
      series={[{ field: "jobs", label: t("Scheduled"), color: colors.primaryPressed }, { field: "completed", label: t("Completed"), color: colors.success }, { field: "cancelled", label: t("Cancelled"), color: colors.danger }]} />
  </>;
}
function Chart({ title, subtitle, points, series, currency }: { title: string; subtitle: string; points: ChartPoint[]; series: Series[]; currency?: string }) {
  const viewport = Math.min(useWindowDimensions().width, 1200) - 64;
  const width = Math.max(viewport, 80 + points.length * 74);
  const left = currency ? 84 : 36;
  const plotHeight = 170, top = 30, bottom = top + plotHeight;
  const group = (width - left - 16) / Math.max(points.length, 1);
  const barWidth = Math.min(18, (group - 18) / series.length);
  const axis = chartAxis(Math.max(0, ...points.flatMap(point => series.map(item => point[item.field]))), !currency);
  const money = (value: number) => new Intl.NumberFormat(staffLocale(), { style: "currency", currency: currency ?? "AED", maximumFractionDigits: 2 }).format(value / 100);
  const valueText = (value: number) => currency ? money(value) : String(value);
  const dateLabel = (date: string) => new Intl.DateTimeFormat(staffLocale(), { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
  return <Card>
    <Text accessibilityRole="header" style={styles.title}>{title}</Text>
    <Text style={uiStyles.muted}>{subtitle}</Text>
    <View style={styles.legend}>{series.map(item => <View key={item.field} style={styles.legendItem}><View style={[styles.swatch, { backgroundColor: item.color }]} /><Text style={styles.label}>{item.label}</Text></View>)}</View>
    {width > viewport ? <Text style={styles.hint}>{t("Swipe horizontally to view all dates.")}</Text> : null}
    <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{ minWidth: viewport }}>
      <Svg width={width} height={252} role="img" accessibilityLabel={title}>
        {axis.ticks.map(tick => {
          const y = bottom - tick / axis.maximum * plotHeight;
          return <ViewlessTick key={tick} y={y} left={left} width={width} label={valueText(tick)} />;
        })}
        {points.map((point, index) => {
          const center = left + group * (index + 0.5);
          return <SvgGroup key={point.date} center={center} bottom={bottom} barWidth={barWidth} plotHeight={plotHeight} maximum={axis.maximum} point={point} series={series} dateLabel={dateLabel(point.date)} />;
        })}
      </Svg>
    </ScrollView>
    {!currency ? <Text style={styles.hint}>{t("Scheduled includes all bookings in each date group; completed and cancelled are subsets.")}</Text> : null}
    <Disclosure title={t("View chart values")}>
      {points.map(point => <View key={point.date} style={styles.dataRow}>
        <Text style={uiStyles.body}>{dateLabel(point.date)}{point.endDate !== point.date ? t(" – {p0}", { p0: dateLabel(point.endDate) }) : ""}</Text>
        {series.map(item => <Text key={item.field} style={styles.label}>{item.label}: {valueText(point[item.field])}</Text>)}
      </View>)}
    </Disclosure>
  </Card>;
}
function ViewlessTick({ y, left, width, label }: { y: number; left: number; width: number; label: string }) {
  return <><Line x1={left} x2={width - 8} y1={y} y2={y} stroke={colors.border} strokeWidth={1} /><SvgText x={left - 8} y={y + 4} fontSize={11} fill={colors.textSecondary} textAnchor="end">{label}</SvgText></>;
}
function SvgGroup({ center, bottom, barWidth, plotHeight, maximum, point, series, dateLabel }: { center: number; bottom: number; barWidth: number; plotHeight: number; maximum: number; point: ChartPoint; series: Series[]; dateLabel: string }) {
  return <>
    {series.map((item, i) => {
      const height = point[item.field] / maximum * plotHeight;
      return <Rect key={item.field} x={center - series.length * (barWidth + 3) / 2 + i * (barWidth + 3)} y={bottom - height} width={barWidth} height={height} fill={item.color} rx={2} />;
    })}
    <SvgText x={center} y={bottom + 22} textAnchor="middle" fill={colors.textSecondary} fontSize={12}>{dateLabel}</SvgText>
  </>;
}
const styles = StyleSheet.create({
  title: { color: colors.text, fontSize: 20, fontWeight: "700" },
  legend: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, paddingVertical: spacing.sm },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  swatch: { width: 12, height: 12, borderRadius: 2 },
  label: { color: colors.text, fontSize: 13, lineHeight: 20 },
  hint: { color: colors.textSecondary, fontSize: 12, lineHeight: 18 },
  dataRow: { gap: 3, paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
});
