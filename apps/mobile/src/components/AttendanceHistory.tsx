import { useState } from "react";
import { Platform, Text, TextInput, View } from "react-native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { operationalScope } from "../cache/policy";
import { staffLocale, t } from "../i18n";
import { domainErrorMessage } from "../errors/domainErrors";
import {
  correctAttendance,
  getAttendance,
  type Attendance,
  type StaffContext,
} from "../lib";
import {
  useAttendanceHistoryQuery,
  useStaffQuery,
} from "../queries/operations";
import {
  addUaeDays,
  formatUaeDate,
  formatUaeDateTime,
  uaeDateKey,
  uaeTimeValue,
  wallDate,
} from "../time/uaeTime";
import { spacing } from "../theme";
import { DatePickerField, TimePickerField } from "./pickers";
import {
  AppButton,
  Card,
  Disclosure,
  EmptyState,
  Skeleton,
  StatusChip,
  uiStyles,
} from "./ui";

function duration(minutes: number) {
  const format = new Intl.NumberFormat(staffLocale());
  return t("{hours} h {minutes} min", {
    hours: format.format(Math.floor(minutes / 60)),
    minutes: format.format(minutes % 60),
  });
}

export function AttendanceHistory({
  context,
  management = false,
}: {
  context: StaffContext;
  management?: boolean;
}) {
  return (
    <Disclosure title={t("Attendance history")}>
      <History context={context} management={management} />
    </Disclosure>
  );
}

function History({
  context,
  management,
}: {
  context: StaffContext;
  management: boolean;
}) {
  const today = uaeDateKey();
  const [start, setStart] = useState(() => addUaeDays(today, -29));
  const [end, setEnd] = useState(today);
  const [staff, setStaff] = useState<string | undefined>(
    management ? undefined : context.staff_id,
  );
  const [offset, setOffset] = useState(0);
  const query = useAttendanceHistoryQuery(context, start, end, offset, staff);
  const exportCsv = useMutation({
    mutationFn: async () => {
      const rows = [
        [
          "Employee",
          "Abu Dhabi work date",
          "Clock-in (UTC)",
          "Clock-out (UTC)",
          "Break minutes",
          "Worked minutes",
          "Status",
        ],
      ];
      let next: number | null = 0;
      while (next !== null) {
        const page = await getAttendance(start, end, next, staff);
        for (const item of page.items) {
          const employee = /^\s*[=+\-@]|^[\t\r\n]/.test(item.staff_name)
            ? "'" + item.staff_name
            : item.staff_name;
          rows.push([
            employee,
            item.work_date,
            item.clock_in_at,
            item.clock_out_at ?? "",
            String(item.break_minutes ?? ""),
            item.clock_out_at ? String(item.worked_minutes) : "",
            item.status,
          ]);
        }
        next = page.next_offset;
      }
      const csv = rows
        .map((row) =>
          row.map((value) => '"' + value.replaceAll('"', '""') + '"').join(","),
        )
        .join("\r\n");
      const url = URL.createObjectURL(
        new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }),
      );
      const download = document.createElement("a");
      download.href = url;
      download.download = `attendance-${start}-${end}.csv`;
      download.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  });
  const groups = new Map<string, Attendance[]>();
  for (const item of query.data?.items ?? []) {
    const day = item.work_date || uaeDateKey(item.clock_in_at);
    groups.set(day, [...(groups.get(day) ?? []), item]);
  }
  return (
    <>
      <Text style={uiStyles.muted}>
        {t("Abu Dhabi time · Sessions grouped by clock-in date")}
      </Text>
      <DatePickerField
        label={t("From")}
        value={start}
        maximumDate={wallDate(end)}
        onChange={(value) => {
          setStart(value);
          setOffset(0);
        }}
      />
      <DatePickerField
        label={t("To")}
        value={end}
        minimumDate={wallDate(start)}
        maximumDate={wallDate(today)}
        onChange={(value) => {
          setEnd(value);
          setOffset(0);
        }}
      />
      {management && (
        <EmployeeFilter
          context={context}
          value={staff}
          onChange={(id) => {
            setStaff(id);
            setOffset(0);
          }}
        />
      )}
      {management && Platform.OS === "web" && (
        <>
          <AppButton
            title={t("Export attendance CSV")}
            tone="secondary"
            loading={exportCsv.isPending}
            disabled={!query.data?.items.length}
            onPress={() => exportCsv.mutate()}
          />
          {exportCsv.isError && (
            <Text accessibilityRole="alert" style={uiStyles.error}>
              {domainErrorMessage(exportCsv.error, "Attendance export failed.")}
            </Text>
          )}
        </>
      )}
      {query.isPending ? (
        <Skeleton rows={2} />
      ) : query.isError ? (
        <EmptyState
          title={t("Attendance could not load.")}
          body={domainErrorMessage(query.error, "Please retry.")}
          action={
            <AppButton
              title={t("Try again")}
              onPress={() => void query.refetch()}
            />
          }
        />
      ) : !groups.size ? (
        <EmptyState title={t("No attendance in this date range")} />
      ) : (
        <>
          <Text accessibilityRole="header" style={uiStyles.label}>
            {t("Period total")} ·{" "}
            {duration(query.data?.total_worked_minutes ?? 0)}
          </Text>
          {[...groups].map(([day, items]) => (
            <View key={day} style={{ gap: spacing.sm }}>
              <Text accessibilityRole="header" style={uiStyles.label}>
                {formatUaeDate(day + "T12:00:00+04:00")} ·{" "}
                {duration(query.data?.daily_worked_minutes?.[day] ?? 0)}
              </Text>
              {items.map((item) => (
                <HistoryEntry
                  key={item.id}
                  item={item}
                  context={context}
                  management={management}
                />
              ))}
            </View>
          ))}
        </>
      )}
      {offset > 0 && (
        <AppButton
          title={t("Previous")}
          tone="secondary"
          onPress={() => setOffset(Math.max(0, offset - 50))}
        />
      )}
      {query.data?.next_offset != null && (
        <AppButton
          title={t("Next")}
          tone="secondary"
          onPress={() => setOffset(query.data?.next_offset ?? 0)}
        />
      )}
    </>
  );
}

function EmployeeFilter({
  context,
  value,
  onChange,
}: {
  context: StaffContext;
  value?: string;
  onChange: (id?: string) => void;
}) {
  const people = useStaffQuery(context);
  const name = people.data?.find((item) => item.id === value)?.display_name;
  const [search, setSearch] = useState("");
  const options = people.data?.filter((item) =>
    item.display_name
      .toLocaleLowerCase()
      .includes(search.trim().toLocaleLowerCase()),
  );
  return (
    <Disclosure title={t("Employee filter") + " · " + (name ?? t("All staff"))}>
      <TextInput
        style={uiStyles.field}
        value={search}
        onChangeText={setSearch}
        accessibilityLabel={t("Find employee")}
        placeholder={t("Find employee")}
      />
      {people.isPending && <Skeleton rows={2} />}
      {people.isError && (
        <AppButton
          title={t("Try again")}
          onPress={() => void people.refetch()}
        />
      )}
      <AppButton
        title={t("All staff")}
        tone={value ? "secondary" : "primary"}
        onPress={() => onChange()}
      />
      {options?.map((item) => (
        <AppButton
          key={item.id}
          title={item.display_name}
          tone={value === item.id ? "primary" : "secondary"}
          onPress={() => onChange(item.id)}
        />
      ))}
    </Disclosure>
  );
}

function HistoryEntry({
  item,
  context,
  management,
}: {
  item: Attendance;
  context: StaffContext;
  management: boolean;
}) {
  return (
    <Card>
      {management && <Text style={uiStyles.body}>{item.staff_name}</Text>}
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          alignItems: "center",
          gap: spacing.sm,
        }}
      >
        <StatusChip value={item.clock_out_at ? item.status : "incomplete"} />
        <Text style={uiStyles.body}>
          {item.clock_out_at
            ? duration(item.worked_minutes)
            : t("Clock-out missing")}
        </Text>
      </View>
      <Text style={uiStyles.body}>
        {t("Clock in")} · {formatUaeDateTime(item.clock_in_at)}
      </Text>
      <Text style={uiStyles.body}>
        {t("Clock out")} ·{" "}
        {item.clock_out_at
          ? formatUaeDateTime(item.clock_out_at)
          : t("Not recorded")}
      </Text>
      {item.break_minutes != null && (
        <Text style={uiStyles.muted}>
          {t("Break")} · {duration(item.break_minutes)}
        </Text>
      )}
      <Disclosure title={t("Attendance details")}>
        <Text style={uiStyles.body}>
          {t("Minutes late")} ·{" "}
          {new Intl.NumberFormat(staffLocale()).format(item.late_minutes)}
        </Text>
        {item.corrections?.map((entry, index) => (
          <View key={entry.occurred_at + index} style={{ gap: spacing.xs }}>
            <Text style={uiStyles.label}>
              {t("Approved correction")} ·{" "}
              {formatUaeDateTime(entry.occurred_at)}
            </Text>
            <Text style={uiStyles.body}>{entry.reason}</Text>
            <Text style={uiStyles.body}>
              {t("Original clock in")} ·{" "}
              {formatUaeDateTime(entry.before.clock_in_at)}
            </Text>
            <Text style={uiStyles.body}>
              {t("Original clock out")} ·{" "}
              {entry.before.clock_out_at
                ? formatUaeDateTime(entry.before.clock_out_at)
                : t("Not recorded")}
            </Text>
            {entry.before.break_minutes != null && (
              <Text style={uiStyles.body}>
                {t("Original break")} · {duration(entry.before.break_minutes)}
              </Text>
            )}
          </View>
        ))}
        {management && (
          <Disclosure title={t("Correct attendance")}>
            <CorrectionForm item={item} context={context} />
          </Disclosure>
        )}
      </Disclosure>
    </Card>
  );
}

function CorrectionForm({
  item,
  context,
}: {
  item: Attendance;
  context: StaffContext;
}) {
  const client = useQueryClient();
  const scope = operationalScope(context);
  const [inDay, setInDay] = useState(() => uaeDateKey(item.clock_in_at));
  const [inTime, setInTime] = useState(() => uaeTimeValue(item.clock_in_at));
  const [outDay, setOutDay] = useState(() =>
    uaeDateKey(item.clock_out_at ?? item.clock_in_at),
  );
  const [outTime, setOutTime] = useState(() =>
    item.clock_out_at ? uaeTimeValue(item.clock_out_at) : "",
  );
  const [breakText, setBreakText] = useState(
    item.break_minutes?.toString() ?? "",
  );
  const [reason, setReason] = useState("");
  const breakDigits = breakText
    .trim()
    .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 1632))
    .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 1776));
  const mutation = useMutation({
    mutationFn: () =>
      correctAttendance(item.id, {
        clock_in_at: `${inDay}T${inTime.slice(0, 5)}:00+04:00`,
        clock_out_at: `${outDay}T${outTime.slice(0, 5)}:00+04:00`,
        break_minutes: breakDigits ? Number(breakDigits) : null,
        reason: reason.trim(),
      }),
    onSuccess: async () => {
      setReason("");
      await Promise.all(
        ["attendance", "attendance-history", "dashboard", "reports"].map(
          (key) => client.invalidateQueries({ queryKey: [key, scope] }),
        ),
      );
    },
  });
  return (
    <>
      <DatePickerField
        label={t("Clock-in date")}
        value={inDay}
        onChange={setInDay}
      />
      <TimePickerField
        label={t("Clock in")}
        value={inTime}
        onChange={setInTime}
      />
      <DatePickerField
        label={t("Clock-out date")}
        value={outDay}
        onChange={setOutDay}
      />
      <TimePickerField
        label={t("Clock out")}
        value={outTime || "12:00"}
        onChange={setOutTime}
      />
      {!outTime && (
        <Text style={uiStyles.muted}>
          {t("Select the actual clock-out time.")}
        </Text>
      )}
      <TextInput
        style={uiStyles.field}
        accessibilityLabel={t("Break minutes (optional)")}
        placeholder={t("Break minutes (optional)")}
        keyboardType="number-pad"
        value={breakText}
        onChangeText={setBreakText}
      />
      <TextInput
        style={uiStyles.field}
        accessibilityLabel={t("Correction reason")}
        placeholder={t("Correction reason")}
        value={reason}
        onChangeText={setReason}
        maxLength={500}
      />
      {mutation.isError && (
        <Text accessibilityRole="alert" style={uiStyles.error}>
          {domainErrorMessage(mutation.error, "Attendance not changed")}
        </Text>
      )}
      {mutation.isSuccess && (
        <Text accessibilityLiveRegion="polite" style={uiStyles.body}>
          {t("Correction saved")}
        </Text>
      )}
      <AppButton
        title={t("Save correction")}
        loading={mutation.isPending}
        disabled={
          !outTime || reason.trim().length < 2 || !/^\d*$/.test(breakDigits)
        }
        onPress={() => mutation.mutate()}
      />
    </>
  );
}
