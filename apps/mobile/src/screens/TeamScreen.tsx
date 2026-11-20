import { AttendanceHistory } from "../components/AttendanceHistory";
import { formatUaeTime } from "../time/uaeTime";
import { t } from "../i18n";
import { Alert } from "../alert";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  DatePickerField,
  TimePickerField,
} from "../components/pickers";
import {
  AppButton,
  Card,
  EmptyState,
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { successHaptic } from "../haptics";
import {
  resetStaffPassword,
  type Attendance,
  type AttendanceOverview,
  type Cancellation,
  type Job,
  type Leave,
  type Performance,
  type Profile,
  type Shift,
  type ShiftAssignment,
  type StaffContext,
  type Team,
  type TeamDetail,
  type TeamStockSummary,
} from "../lib";
import {
  addUaeDays,
  formatUaeDateTime,
  uaeDateKey,
  wallDate,
} from "../time/uaeTime";
import { ApiError, domainErrorMessage } from "../errors/domainErrors";
import {
  eligibleTeamsForStaff,
  normalizeStaffPhone,
  normalizeStaffUsername,
  validateAddStaff,
} from "../forms/staffForm";
import { validatePasswordConfirmation } from "../forms/password";
import {
  useAssignShiftMutation,
  useAttendanceOverviewQuery,
  useCancellationsQuery,
  useCreateShiftMutation,
  useCreateStaffMutation,
  useCreateTeamMutation,
  useJobsQuery,
  useLeaveQuery,
  useReportQuery,
  useReviewCancellationMutation,
  useReviewLeaveMutation,
  useShiftAssignmentsQuery,
  useShiftsQuery,
  useStaffQuery,
  useTeamQuery,
  useTeamStockSummaryQuery,
  useTeamsQuery,
  useUpdateStaffMutation,
  useUpdateTeamMutation,
  useUpdateTeamMembersMutation,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";
import { sameStringSet } from "../operations";

export type TeamSection = "teams" | "staff" | "shifts" | "attendance";
const teamSectionLabels: Record<TeamSection, string> = {
  teams: "Teams",
  staff: "Staff",
  shifts: "Shifts",
  attendance: "Attendance",
};
export function TeamScreen({
  context,
  initialSection = "teams",
  onSectionChange,
}: {
  context: StaffContext;
  initialSection?: TeamSection;
  onSectionChange?: (value: TeamSection) => void;
}) {
  const [section, setSection] = useState<TeamSection>(initialSection);
  return (
    <View style={{ flex: 1 }}>
      <View style={styles.segment}>
        {(["teams", "staff", "shifts", "attendance"] as const).map((item) => (
          <Pressable
            key={item}
            accessibilityRole="tab"
            accessibilityState={{ selected: section === item }}
            onPress={() => {
              setSection(item);
              onSectionChange?.(item);
            }}
            style={[
              styles.segmentItem,
              section === item ? styles.segmentActive : undefined,
            ]}
          >
            <Text
              style={[
                styles.segmentText,
                section === item ? styles.segmentTextActive : undefined,
              ]}
            >
              {t(teamSectionLabels[item])}
            </Text>
          </Pressable>
        ))}
      </View>
      {section === "teams" ? (
        <TeamsPane context={context} />
      ) : section === "staff" ? (
        <StaffPane context={context} />
      ) : section === "shifts" ? (
        <ShiftsPane context={context} />
      ) : (
        <AttendancePane context={context} />
      )}
    </View>
  );
}

function TeamsPane({ context }: { context: StaffContext }) {
  const teamsQuery = useTeamsQuery(context);
  const staffQuery = useStaffQuery(context);
  const createMutation = useCreateTeamMutation(context);
  const updateMutation = useUpdateTeamMutation(context);
  const membersMutation = useUpdateTeamMembersMutation(context);
  const items = teamsQuery.data ?? [];
  const [add, setAdd] = useState(false);
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const detailQuery = useTeamQuery(
    context,
    selectedTeamId,
    Boolean(selectedTeamId),
  );
  const teamStock = useTeamStockSummaryQuery(
    context,
    selectedTeamId,
    Boolean(selectedTeamId),
  );
  if (add) {
    return (
      <SimpleCreate
        visible
        title={t("Create team")}
        label={t("TEAM NAME")}
        placeholder={t("Mobile Team 2")}
        onClose={() => setAdd(false)}
        onSave={async (name) => {
          await createMutation.mutateAsync(name);
          await successHaptic();
          setAdd(false);
        }}
      />
    );
  }
  if (selectedTeamId && detailQuery.isPending) {
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <Pressable onPress={() => setSelectedTeamId("")}>
          <Text style={uiStyles.link}>{t("← Teams")}</Text>
        </Pressable>
        <Skeleton rows={5} />
      </ScrollView>
    );
  }
  if (selectedTeamId && detailQuery.isError && !detailQuery.data) {
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <Pressable onPress={() => setSelectedTeamId("")}>
          <Text style={uiStyles.link}>{t("← Teams")}</Text>
        </Pressable>
        <Text style={uiStyles.error}>
          {domainErrorMessage(detailQuery.error, "Team details could not load.")}
        </Text>
        <AppButton
          title={t("Try again")}
          onPress={() => void detailQuery.refetch()}
        />
      </ScrollView>
    );
  }
  if (detailQuery.data) {
    const detail = detailQuery.data;
    return (
      <TeamMembersSheet
        detail={detail}
        stock={teamStock.data ?? null}
        staff={(staffQuery.data ?? []).filter((member) => member.is_active)}
        saving={membersMutation.isPending}
        updating={updateMutation.isPending}
        onSave={(staffIds) =>
          membersMutation.mutateAsync({ teamId: detail.id, staffIds })
        }
        onUpdate={(body) =>
          updateMutation.mutateAsync({ teamId: detail.id, body })
        }
        onClose={() => setSelectedTeamId("")}
        onSaved={() => undefined}
        onMembersSaved={() => {
          setSelectedTeamId("");
        }}
      />
    );
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title={t("Teams")}
        subtitle={t("Scheduling capacity and live workload")}
      />
      <AppButton
        title={t("Create team")}
        tone="secondary"
        onPress={() => setAdd(true)}
      />
      {teamsQuery.isError && items.length ? (
        <Text style={uiStyles.error}>
          {" " + t("Teams could not refresh. Showing saved data.") + " "}</Text>
      ) : null}
      {teamsQuery.isPending ? (
        <Skeleton />
      ) : teamsQuery.isError && !items.length ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(teamsQuery.error, "Teams could not load.")}
        </Text>
      ) : items.length ? (
        items.map((item) => (
          <Pressable key={item.id} onPress={() => setSelectedTeamId(item.id)}>
            <Card>
              <View style={uiStyles.row}>
                <View>
                  <Text style={styles.cardTitle}>{item.name}</Text>
                  <Text style={uiStyles.muted}>
                    {item.member_count} {" " + t("members ·") + " "}{item.jobs_today} {" " + t("jobs today") + " "}</Text>
                </View>
                <StatusChip
                  value={
                    item.is_active
                      ? (item.active_job_status ?? "available")
                      : "inactive"
                  }
                />
              </View>
              {item.active_job_reference ? (
                <Text style={styles.live}>● {item.active_job_reference}</Text>
              ) : null}
              <Text style={uiStyles.link}>{t("Manage members →")}</Text>
            </Card>
          </Pressable>
        ))
      ) : (
        <EmptyState
          title={t("No teams yet")}
          body={t("Create the first mobile team to add booking capacity.")}
        />
      )}
    </ScrollView>
  );
}

function StaffPane({ context }: { context: StaffContext }) {
  const staffQuery = useStaffQuery(context);
  const createStaffMutation = useCreateStaffMutation(context);
  const updateStaffMutation = useUpdateStaffMutation(context);
  const attendance = useAttendanceOverviewQuery(context);
  const today = uaeDateKey();
  const jobs = useJobsQuery(context, {
    view: "today",
    scope: "all",
    date: today,
    limit: 100,
  });
  const report = useReportQuery(
    context,
    addUaeDays(today, -29),
    today,
  );
  const items = staffQuery.data ?? [];
  const [add, setAdd] = useState(false);
  const [selected, setSelected] = useState<Profile | null>(null);
  const [editTarget, setEditTarget] = useState<Profile | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<Profile | null>(null);
  const [updatingStaffId, setUpdatingStaffId] = useState<string | null>(null);
  async function toggle(item: Profile) {
    setUpdatingStaffId(item.id);
    try {
      await updateStaffMutation.mutateAsync({
        staffId: item.id,
        body: { is_active: !item.is_active },
      });
      await successHaptic();
    } catch (error) {
      Alert.alert(
        t("Update failed"),
        domainErrorMessage(error, "The account could not be changed."),
      );
    } finally {
      setUpdatingStaffId(null);
    }
  }
  if (add) {
    return (
      <AddStaffSheet
        visible
        canCreateManager={context.role === "admin"}
        createAccount={(body) => createStaffMutation.mutateAsync(body)}
        onClose={() => setAdd(false)}
        onCreated={() => {
          setAdd(false);
        }}
      />
    );
  }
  if (editTarget) {
    return (
      <EditStaffSheet
        profile={editTarget}
        updateAccount={(body) =>
          updateStaffMutation.mutateAsync({ staffId: editTarget.id, body })
        }
        onClose={() => setEditTarget(null)}
        onSaved={() => {
          setEditTarget(null);
        }}
      />
    );
  }
  if (passwordTarget) {
    return (
      <PasswordSheet
        profile={passwordTarget}
        onClose={() => setPasswordTarget(null)}
      />
    );
  }
  if (selected) {
    return (
      <StaffDetailSheet
        profile={selected}
        attendance={attendance.data?.find(
          (item) => item.staff_id === selected.id,
        )}
        jobs={(jobs.data?.jobs ?? []).filter(
          (item) => item.assigned_staff_id === selected.id,
        )}
        performance={report.data?.staff_performance.find(
          (item) => item.id === selected.id,
        )}
        onClose={() => setSelected(null)}
      />
    );
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title={t("Staff")}
        subtitle={t("Accounts, roles and team membership")}
      />
      <AppButton title={t("Add employee")} onPress={() => setAdd(true)} />
      {staffQuery.isError && items.length ? (
        <Text style={uiStyles.error}>
          {" " + t("Staff could not refresh. Showing saved data.") + " "}</Text>
      ) : null}
      {staffQuery.isPending ? (
        <Skeleton />
      ) : staffQuery.isError && !items.length ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(staffQuery.error, "Staff could not load.")}
        </Text>
      ) : (
        items.map((item) => (
          <Card key={item.id}>
            <Pressable
              accessibilityRole="button"
              onPress={() => setSelected(item)}
            >
              <View style={uiStyles.row}>
                <View style={styles.personRow}>
                  <View style={styles.avatar}>
                    <Text style={styles.initials}>
                      {initials(item.display_name)}
                    </Text>
                  </View>
                  <View>
                    <Text style={styles.cardTitle}>{item.display_name}</Text>
                    <Text style={uiStyles.muted}>
                      @{item.username} · {item.role}
                    </Text>
                  </View>
                </View>
                <StatusChip value={item.is_active ? "active" : "inactive"} />
              </View>
              <Text style={uiStyles.muted}>
                {item.phone ?? t("No phone")}
                {item.teams.length
                  ? t(" · {p0}", { p0: item.teams.map((team) => team.name).join(", ") })
                  : ""}
              </Text>
              <Text style={uiStyles.link}>{t("View attendance & performance →")}</Text>
            </Pressable>
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title={t("Edit")}
                  tone="secondary"
                  onPress={() => setEditTarget(item)}
                />
              </View>
              {item.id !== context.staff_id &&
              (context.role === "admin"
                ? item.role !== "admin"
                : item.role === "employee") ? (
                <View style={{ flex: 1 }}>
                  <AppButton
                    title={t("Reset password")}
                    tone="secondary"
                    onPress={() => setPasswordTarget(item)}
                  />
                </View>
              ) : null}
            </View>
            <AppButton
              title={
                updatingStaffId === item.id
                  ? t("Saving…")
                  : item.is_active
                    ? t("Deactivate")
                    : t("Reactivate")
              }
              tone={item.is_active ? "danger" : "secondary"}
              disabled={updatingStaffId === item.id}
              loading={updatingStaffId === item.id}
              onPress={() => void toggle(item)}
            />
          </Card>
        ))
      )}
    </ScrollView>
  );
}

function ShiftsPane({ context }: { context: StaffContext }) {
  const shiftsQuery = useShiftsQuery(context);
  const assignmentsQuery = useShiftAssignmentsQuery(context);
  const staffQuery = useStaffQuery(context);
  const teamsQuery = useTeamsQuery(context);
  const [add, setAdd] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const shifts = shiftsQuery.data ?? [];
  const assignments = assignmentsQuery.data ?? [];
  const staff = (staffQuery.data ?? []).filter((item) => item.is_active);
  const teams = (teamsQuery.data ?? []).filter((item) => item.is_active);
  const loading =
    shiftsQuery.isPending ||
    assignmentsQuery.isPending ||
    staffQuery.isPending ||
    teamsQuery.isPending;
  const error =
    shiftsQuery.error ??
    assignmentsQuery.error ??
    staffQuery.error ??
    teamsQuery.error;
  if (add) {
    return (
      <CreateShiftSheet
        visible
        context={context}
        onClose={() => setAdd(false)}
      />
    );
  }
  if (assigning) {
    return (
      <ShiftAssignmentSheet
        visible
        context={context}
        shifts={shifts}
        staff={staff}
        teams={teams}
        onClose={() => setAssigning(false)}
      />
    );
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title={t("Shifts")}
        subtitle={t("Today · assigned work and reusable templates")}
      />
      <View style={styles.actions}>
        <View style={{ flex: 1 }}>
          <AppButton
            title={t("Create shift")}
            tone="secondary"
            onPress={() => setAdd(true)}
          />
        </View>
        <View style={{ flex: 1 }}>
          <AppButton title={t("Assign shift")} onPress={() => setAssigning(true)} />
        </View>
      </View>
      {error ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(error, "We couldn't load shifts. Pull to retry.")}
        </Text>
      ) : null}
      {loading ? (
        <Skeleton />
      ) : assignments.length ? (
        assignments.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.staff_name}</Text>
            <Text style={uiStyles.body}>
              {item.shift_name} · {item.start_time.slice(0, 5)}–
              {item.end_time.slice(0, 5)}
            </Text>
            <Text style={uiStyles.muted}>{item.team_name ?? t("No team")}</Text>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No shifts assigned today")} />
      )}
      {shifts.length ? (
        <Text style={uiStyles.muted}>
          {shifts.length} {" " + t("shift templates available") + " "}</Text>
      ) : null}
    </ScrollView>
  );
}

function AttendancePane({ context }: { context: StaffContext }) {
  const attendance = useAttendanceOverviewQuery(context);
  const leaveQuery = useLeaveQuery(context, "pending");
  const cancellationsQuery = useCancellationsQuery(context);
  const leaveDecision = useReviewLeaveMutation(context);
  const cancellationDecision = useReviewCancellationMutation(context);
  const items = attendance.data ?? [];
  const leave = leaveQuery.data ?? [];
  const cancellations = cancellationsQuery.data ?? [];
  const [decisionKey, setDecisionKey] = useState<string | null>(null);
  async function decideLeave(item: Leave, decision: "approved" | "rejected") {
    const key = `${item.id}:${decision}`;
    setDecisionKey(key);
    try {
      await leaveDecision.mutateAsync({ id: item.id, decision });
      await successHaptic();
    } catch (reason) {
      Alert.alert(
        t("Decision not saved"),
        domainErrorMessage(reason, "Please retry."),
      );
    } finally {
      setDecisionKey(null);
    }
  }
  async function decideCancellation(
    item: Cancellation,
    decision: "approved" | "rejected",
  ) {
    const key = `${item.id}:${decision}`;
    setDecisionKey(key);
    try {
      await cancellationDecision.mutateAsync({ id: item.id, decision });
      await successHaptic();
    } catch (error) {
      Alert.alert(
        t("Decision not saved"),
        domainErrorMessage(error, "Please retry."),
      );
    } finally {
      setDecisionKey(null);
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title={t("Attendance")}
        subtitle={t("Today’s team attendance")}
      />
      <AttendanceHistory context={context} management />
      {attendance.isError && items.length ? (
        <Text style={uiStyles.error}>
          {" " + t("Attendance could not refresh. Showing saved data.") + " "}</Text>
      ) : null}
      {attendance.isPending ? (
        <Skeleton />
      ) : attendance.isError && !items.length ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(attendance.error, "Attendance could not load.")}
        </Text>
      ) : (
        items.map((item) => (
          <Card key={item.staff_id}>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>{item.staff_name}</Text>
                <Text style={uiStyles.muted}>
                  {item.shift_name
                    ? t("{p0} · {p1}–{p2}", { p0: item.shift_name, p1: item.shift_start?.slice(0, 5), p2: item.shift_end?.slice(0, 5) })
                    : t("No shift today")}
                </Text>
              </View>
              <StatusChip value={item.status} />
            </View>
            {item.clock_in_at ? (
              <Text style={uiStyles.muted}>
                {formatUaeTime(item.clock_in_at)}{" "}
                →{" "}
                {item.clock_out_at
                  ? formatUaeTime(item.clock_out_at)
                  : t("Now")}
              </Text>
            ) : null}
            {item.late_minutes ? (
              <Text style={styles.warning}>{item.late_minutes} {" " + t("min late") + ""}</Text>
            ) : null}
            {item.missed_shift ? (
              <Text style={styles.warning}>{t("Missed shift")}</Text>
            ) : null}
          </Card>
        ))
      )}
      <Text style={styles.section}>{t("PENDING LEAVE")}</Text>
      {leave.length ? (
        leave.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.staff_name}</Text>
            <Text style={uiStyles.body}>
              {item.start_date}
              {item.end_date !== item.start_date ? t(" → {p0}", { p0: item.end_date }) : ""}
            </Text>
            <Text style={uiStyles.muted}>{item.reason}</Text>
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title={
                    decisionKey === `${item.id}:rejected`
                      ? t("Rejecting…")
                      : t("Reject")
                  }
                  tone="danger"
                  disabled={decisionKey !== null}
                  loading={decisionKey === `${item.id}:rejected`}
                  onPress={() => void decideLeave(item, "rejected")}
                />
              </View>
              <View style={{ flex: 1 }}>
                <AppButton
                  title={
                    decisionKey === `${item.id}:approved`
                      ? t("Approving…")
                      : t("Approve")
                  }
                  disabled={decisionKey !== null}
                  loading={decisionKey === `${item.id}:approved`}
                  onPress={() => void decideLeave(item, "approved")}
                />
              </View>
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No pending leave requests")} />
      )}
      <Text style={styles.section}>{t("CANCELLATIONS")}</Text>
      {cancellationsQuery.isError && cancellations.length ? (
        <Text style={uiStyles.error}>
          {" " + t("Cancellation requests could not refresh. Showing saved data.") + " "}</Text>
      ) : null}
      {cancellationsQuery.isPending ? (
        <Skeleton />
      ) : cancellationsQuery.isError && !cancellations.length ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(
            cancellationsQuery.error,
            "Cancellation requests could not load.",
          )}
        </Text>
      ) : cancellations.length ? (
        cancellations.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.customer_name}</Text>
            <Text style={uiStyles.body}>
              {item.booking_reference} ·{" "}
              {formatUaeDateTime(item.scheduled_start)}
            </Text>
            <Text style={uiStyles.muted}>
              {item.reason ?? t("No reason provided")}
            </Text>
            <StatusChip value={item.payment_status} />
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title={
                    decisionKey === `${item.id}:rejected`
                      ? t("Rejecting…")
                      : t("Reject")
                  }
                  tone="danger"
                  disabled={decisionKey !== null}
                  loading={decisionKey === `${item.id}:rejected`}
                  onPress={() => void decideCancellation(item, "rejected")}
                />
              </View>
              <View style={{ flex: 1 }}>
                <AppButton
                  title={
                    decisionKey === `${item.id}:approved`
                      ? t("Approving…")
                      : t("Approve")
                  }
                  disabled={decisionKey !== null}
                  loading={decisionKey === `${item.id}:approved`}
                  onPress={() => void decideCancellation(item, "approved")}
                />
              </View>
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No cancellation requests")} />
      )}
    </ScrollView>
  );
}

function AddStaffSheet({
  visible,
  canCreateManager,
  onClose,
  onCreated,
  createAccount,
}: {
  visible: boolean;
  canCreateManager: boolean;
  onClose: () => void;
  onCreated: (profile: Profile) => void;
  createAccount: (body: object) => Promise<Profile>;
}) {
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"employee" | "manager">("employee");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");
  const errors = validateAddStaff({ name, username, phone, password });
  const formValid = Object.keys(errors).length === 0;
  async function save() {
    if (!formValid) return;
    setBusy(true);
    setFormError("");
    try {
      const profile = await createAccount({
        display_name: name.trim(),
        username: normalizeStaffUsername(username),
        phone: normalizeStaffPhone(phone),
        role,
        temporary_password: password,
      });
      await successHaptic();
      onCreated(profile);
    } catch (reason) {
      setFormError(
        domainErrorMessage(reason, "Check the details and try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  if (!visible) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{t("Add staff")}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <View>
        <Text style={uiStyles.label}>{t("FULL NAME")}</Text>
        <TextInput
          accessibilityLabel={t("Full name")}
          style={uiStyles.field}
          value={name}
          onChangeText={setName}
          placeholder={t("Mohammed Ali")}
          autoCapitalize="words"
        />
        {errors.name ? <Text style={uiStyles.error}>{errors.name}</Text> : null}
      </View>
      <View>
        <Text style={uiStyles.label}>{t("USERNAME")}</Text>
        <TextInput
          accessibilityLabel={t("Username")}
          style={uiStyles.field}
          value={username}
          onChangeText={(value) => setUsername(normalizeStaffUsername(value))}
          placeholder={t("mohammed.ali")}
          autoCapitalize="none"
          autoCorrect={false}
        />
        {errors.username ? (
          <Text style={uiStyles.error}>{errors.username}</Text>
        ) : null}
      </View>
      <View>
        <Text style={uiStyles.label}>{t("PHONE")}</Text>
        <TextInput
          accessibilityLabel={t("Phone")}
          style={uiStyles.field}
          value={phone}
          onChangeText={setPhone}
          placeholder="050 555 5555"
          keyboardType="phone-pad"
        />
        <Text style={uiStyles.muted}>
          {" " + t("UAE local and international formats accepted.") + " "}</Text>
        {errors.phone ? (
          <Text style={uiStyles.error}>{errors.phone}</Text>
        ) : null}
      </View>
      <View>
        <Text style={uiStyles.label}>{t("TEMPORARY PASSWORD")}</Text>
        <TextInput
          accessibilityLabel={t("Temporary password")}
          style={uiStyles.field}
          value={password}
          onChangeText={setPassword}
          placeholder={t("At least 8 characters")}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Text style={uiStyles.muted}>{password.length} {" " + t("/ 8 minimum") + ""}</Text>
        {errors.password ? (
          <Text style={uiStyles.error}>{errors.password}</Text>
        ) : null}
      </View>
      {canCreateManager ? (
        <View style={styles.actions}>
          <Pressable
            onPress={() => setRole("employee")}
            style={[
              styles.roleChoice,
              role === "employee" ? styles.roleActive : undefined,
            ]}
          >
            <Text>{t("Employee")}</Text>
          </Pressable>
          <Pressable
            onPress={() => setRole("manager")}
            style={[
              styles.roleChoice,
              role === "manager" ? styles.roleActive : undefined,
            ]}
          >
            <Text>{t("Manager")}</Text>
          </Pressable>
        </View>
      ) : null}
      {formError ? <Text style={uiStyles.error}>{formError}</Text> : null}
      <AppButton
        title={busy ? t("Creating…") : t("Create account")}
        disabled={busy || !formValid}
        loading={busy}
        onPress={() => void save()}
      />
    </ScrollView>
  );
}
function SimpleCreate({
  visible,
  title,
  label,
  placeholder,
  onClose,
  onSave,
}: {
  visible: boolean;
  title: string;
  label: string;
  placeholder: string;
  onClose: () => void;
  onSave: (value: string) => Promise<void>;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  if (!visible) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{title}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <Text style={uiStyles.label}>{label}</Text>
      <TextInput
        style={uiStyles.field}
        value={value}
        onChangeText={setValue}
        placeholder={placeholder}
      />
      <AppButton
        title={busy ? t("Creating…") : t("Create team")}
        disabled={busy || value.trim().length < 2}
        loading={busy}
        onPress={() => {
          setBusy(true);
          void onSave(value.trim())
            .catch((error) =>
              Alert.alert(
                t("Team not created"),
                domainErrorMessage(
                  error,
                  "Something went wrong while creating the team. Please try again.",
                ),
              ),
            )
            .finally(() => setBusy(false));
        }}
      />
    </ScrollView>
  );
}
function TeamMembersSheet({
  detail,
  stock,
  staff,
  saving,
  updating,
  onSave,
  onUpdate,
  onClose,
  onSaved,
  onMembersSaved,
}: {
  detail: TeamDetail | null;
  stock: TeamStockSummary | null;
  staff: Profile[];
  saving: boolean;
  updating: boolean;
  onSave: (staffIds: string[]) => Promise<TeamDetail>;
  onUpdate: (body: object) => Promise<TeamDetail>;
  onClose: () => void;
  onSaved: (team: TeamDetail) => void;
  onMembersSaved: (team: TeamDetail) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [teamName, setTeamName] = useState("");
  useEffect(() => {
    setSelected(detail?.members.map((member) => member.id) ?? []);
    setTeamName(detail?.name ?? "");
  }, [detail?.id]);
  function toggle(id: string) {
    setSelected((values) =>
      values.includes(id)
        ? values.filter((value) => value !== id)
        : [...values, id],
    );
  }
  async function save() {
    if (!detail) return;
    try {
      const next = await onSave(selected);
      await successHaptic();
      onMembersSaved(next);
    } catch (error) {
      Alert.alert(
        t("Members not saved"),
        domainErrorMessage(
          error,
          "The team membership could not be updated. Please try again.",
        ),
      );
    }
  }
  async function saveTeam(body: object) {
    try {
      const next = await onUpdate(body);
      await successHaptic();
      onSaved(next);
    } catch (error) {
      Alert.alert(
        t("Team not updated"),
        domainErrorMessage(
          error,
          "The team details could not be updated. Please try again.",
        ),
      );
    }
  }
  if (!detail) return null;
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{detail.name}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <Text style={uiStyles.muted}>{detail.jobs_today} {" " + t("jobs today") + ""}</Text>
      <Card>
        <Text style={styles.section}>{t("STOCK")}</Text>
        <Text style={styles.cardTitle}>{stock?.location_name ?? t("No linked stock location")}</Text>
        {stock?.items.map((item) => (
          <View key={item.item_id} style={uiStyles.row}>
            <Text style={uiStyles.body}>{item.item_name}</Text>
            <Text style={uiStyles.muted}>{item.quantity} {item.unit}</Text>
          </View>
        ))}
        {stock ? (
          <Text style={uiStyles.muted}>
            {stock.low_stock_count} {" " + t("low ·") + " "}{stock.out_of_stock_count} {" " + t("out") + " "}</Text>
        ) : null}
      </Card>
      <Text style={uiStyles.label}>{t("TEAM NAME")}</Text>
      <TextInput
        style={uiStyles.field}
        value={teamName}
        onChangeText={setTeamName}
      />
      <View style={styles.actions}>
        <View style={{ flex: 1 }}>
          <AppButton
            title={updating ? t("Saving…") : t("Save name")}
            tone="secondary"
            disabled={
              updating ||
              teamName.trim().length < 2 ||
              teamName.trim() === detail.name
            }
            loading={updating}
            onPress={() => void saveTeam({ name: teamName.trim() })}
          />
        </View>
        <View style={{ flex: 1 }}>
          <AppButton
            title={detail.is_active ? t("Deactivate") : t("Reactivate")}
            tone={detail.is_active ? "danger" : "secondary"}
            disabled={updating}
            loading={updating}
            onPress={() => void saveTeam({ is_active: !detail.is_active })}
          />
        </View>
      </View>
      <Text style={styles.section}>{t("MEMBERS")}</Text>
      {staff.map((member) => (
        <Pressable
          key={member.id}
          style={[
            styles.memberChoice,
            selected.includes(member.id) ? styles.memberSelected : undefined,
          ]}
          onPress={() => toggle(member.id)}
        >
          <View>
            <Text style={styles.cardTitle}>{member.display_name}</Text>
            <Text style={uiStyles.muted}>
              @{member.username} · {member.role}
            </Text>
          </View>
          <Text style={styles.check}>
            {selected.includes(member.id) ? "✓" : "+"}
          </Text>
        </Pressable>
      ))}
      <AppButton
        title={saving ? t("Saving…") : t("Save members")}
        disabled={
          saving ||
          sameStringSet(
            selected,
            detail.members.map((member) => member.id),
          )
        }
        loading={saving}
        onPress={() => void save()}
      />
    </ScrollView>
  );
}
function EditStaffSheet({
  profile,
  updateAccount,
  onClose,
  onSaved,
}: {
  profile: Profile | null;
  updateAccount: (body: object) => Promise<Profile>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setName(profile?.display_name ?? "");
    setPhone(profile?.phone ?? "");
  }, [profile]);
  async function save() {
    if (!profile) return;
    setBusy(true);
    try {
      await updateAccount({
        display_name: name.trim(),
        phone: phone.trim() || null,
      });
      await successHaptic();
      onSaved();
    } catch (error) {
      Alert.alert(
        t("Profile not saved"),
        domainErrorMessage(error, "Check the staff details and try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  if (!profile) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{t("Edit staff")}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <Text style={uiStyles.label}>{t("FULL NAME")}</Text>
      <TextInput style={uiStyles.field} value={name} onChangeText={setName} />
      <Text style={uiStyles.label}>{t("PHONE")}</Text>
      <TextInput
        style={uiStyles.field}
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
      />
      <AppButton
        title={busy ? t("Saving…") : t("Save changes")}
        disabled={busy || name.trim().length < 2}
        loading={busy}
        onPress={() => void save()}
      />
      <AppButton title={t("Cancel")} tone="secondary" onPress={onClose} />
    </ScrollView>
  );
}
function StaffDetailSheet({
  profile,
  attendance,
  jobs,
  performance,
  onClose,
}: {
  profile: Profile | null;
  attendance?: AttendanceOverview;
  jobs: Job[];
  performance?: Performance;
  onClose: () => void;
}) {
  if (!profile) return null;
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <View style={uiStyles.row}>
        <View>
          <Text style={styles.sheetTitle}>{profile.display_name}</Text>
          <Text style={uiStyles.muted}>
            @{profile.username} · {profile.role}
          </Text>
        </View>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Close")}</Text>
        </Pressable>
      </View>
      <Text style={styles.section}>{t("TEAMS")}</Text>
      <Text style={uiStyles.body}>
        {profile.teams.length
          ? profile.teams.map((team) => team.name).join(", ")
          : t("No team membership")}
      </Text>
      <Text style={styles.section}>{t("TODAY'S ATTENDANCE")}</Text>
      {attendance ? (
        <Card>
          <StatusChip value={attendance.status} />
          <Text style={uiStyles.muted}>
            {attendance.worked_minutes} {" " + t("minutes worked ·") + ""}{" "}
            {attendance.late_minutes} {" " + t("minutes late") + " "}</Text>
        </Card>
      ) : (
        <EmptyState title={t("No attendance recorded")} />
      )}
      <Text style={styles.section}>{t("TODAY'S JOBS")}</Text>
      <Text style={styles.cardTitle}>{jobs.length}</Text>
      <Text style={styles.section}>{t("LAST 30 DAYS")}</Text>
      {performance ? (
        <Card>
          <Text style={uiStyles.body}>
            {performance.jobs_completed} {" " + t("completed ·") + ""}{" "}
            {performance.hours_worked.toFixed(1)} {" " + t("hours") + " "}</Text>
          <Text style={uiStyles.muted}>
            {" " + t("Average wash") + " "}{performance.average_wash_minutes} {" " + t("min ·") + ""}{" "}
            {performance.late_arrivals} {" " + t("late arrivals") + " "}</Text>
          <Text style={uiStyles.muted}>
            {performance.jobs_per_worked_hour.toFixed(2)} {" " + t("jobs per worked hour") + " "}</Text>
        </Card>
      ) : (
        <EmptyState title={t("No performance data")} />
      )}
    </ScrollView>
  );
}
function PasswordSheet({
  profile,
  onClose,
}: {
  profile: Profile | null;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"choose" | "manual">("choose");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  async function reset(modeToUse: "temporary" | "manual") {
    if (!profile) return;
    if (modeToUse === "manual") {
      const validation = validatePasswordConfirmation(password, confirmation);
      if (validation) {
        Alert.alert(t("Password not changed"), validation);
        return;
      }
    }
    setBusy(true);
    try {
      const result = await resetStaffPassword(profile.id, {
        mode: modeToUse,
        ...(modeToUse === "manual" ? { new_password: password } : {}),
      });
      await successHaptic();
      setPassword("");
      setConfirmation("");
      if (modeToUse === "temporary" && result.temporary_password) {
        Alert.alert(
          t("Password reset successfully."),
          t("Temporary password: {p0}\n\nEmployee must change this password on next login.", { p0: result.temporary_password }),
          [{ text: t("Done"), onPress: onClose }],
        );
      } else {
        Alert.alert(t("Password updated successfully."), undefined, [
          { text: t("Done"), onPress: onClose },
        ]);
      }
    } catch (error) {
      Alert.alert(
        t("Password not changed"),
        domainErrorMessage(
          error,
          "The password could not be changed. Please try again.",
        ),
      );
    } finally {
      setBusy(false);
    }
  }
  if (!profile) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{t("Reset password")}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <Text style={uiStyles.muted}>{profile.display_name}</Text>
      {mode === "choose" ? (
        <>
          <AppButton
            title={t("Reset to temporary password")}
            disabled={busy}
            loading={busy}
            onPress={() =>
              Alert.alert(
                t("Reset password for {p0}?", { p0: profile.display_name }),
                t("A temporary password will be shown once. The employee must change it on next login."),
                [
                  { text: t("Cancel"), style: "cancel" },
                  {
                    text: t("Reset password"),
                    style: "destructive",
                    onPress: () => void reset("temporary"),
                  },
                ],
              )
            }
          />
          <AppButton
            title={t("Set new password manually")}
            tone="secondary"
            disabled={busy}
            onPress={() => setMode("manual")}
          />
        </>
      ) : (
        <>
          <TextInput
            accessibilityLabel={t("New password")}
            autoCapitalize="none"
            style={uiStyles.field}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder={t("New password")}
          />
          <TextInput
            accessibilityLabel={t("Confirm new password")}
            autoCapitalize="none"
            style={uiStyles.field}
            value={confirmation}
            onChangeText={setConfirmation}
            secureTextEntry
            placeholder={t("Confirm new password")}
          />
          <AppButton
            title={busy ? t("Updating…") : t("Update password")}
            disabled={busy}
            loading={busy}
            onPress={() =>
              Alert.alert(t("Reset password for {p0}?", { p0: profile.display_name }), "", [
                { text: t("Cancel"), style: "cancel" },
                {
                  text: t("Update password"),
                  style: "destructive",
                  onPress: () => void reset("manual"),
                },
              ])
            }
          />
          <AppButton
            title={t("Back")}
            tone="secondary"
            disabled={busy}
            onPress={() => setMode("choose")}
          />
        </>
      )}
      <AppButton title={t("Cancel")} tone="secondary" onPress={onClose} />
    </ScrollView>
  );
}
function CreateShiftSheet({
  visible,
  context,
  onClose,
}: {
  visible: boolean;
  context: StaffContext;
  onClose: () => void;
}) {
  const mutation = useCreateShiftMutation(context);
  const [name, setName] = useState("");
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("18:00");
  const valid = name.trim().length >= 2 && startTime < endTime;
  async function save() {
    try {
      await mutation.mutateAsync({
        name: name.trim(),
        start_time: `${startTime}:00`,
        end_time: `${endTime}:00`,
      });
      await successHaptic();
      setName("");
      onClose();
    } catch (error) {
      Alert.alert(
        t("Shift not created"),
        domainErrorMessage(error, "Check the name and times, then try again."),
      );
    }
  }
  if (!visible) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{t("Create shift")}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <Text style={uiStyles.label}>{t("SHIFT NAME")}</Text>
      <TextInput
        accessibilityLabel={t("Shift name")}
        style={uiStyles.field}
        value={name}
        onChangeText={setName}
        placeholder={t("Morning")}
      />
      <TimePickerField
        label={t("Start time")}
        value={startTime}
        onChange={setStartTime}
      />
      <TimePickerField label={t("End time")} value={endTime} onChange={setEndTime} />
      {name && !valid ? (
        <Text style={uiStyles.error}>
          {" " + t("The end time must be after the start time.") + " "}</Text>
      ) : null}
      <AppButton
        title={mutation.isPending ? t("Creating…") : t("Create shift")}
        disabled={mutation.isPending || !valid}
        loading={mutation.isPending}
        onPress={() => void save()}
      />
      <AppButton title={t("Cancel")} tone="secondary" onPress={onClose} />
    </ScrollView>
  );
}
function ShiftAssignmentSheet({
  visible,
  context,
  shifts,
  staff,
  teams,
  onClose,
}: {
  visible: boolean;
  context: StaffContext;
  shifts: Shift[];
  staff: Profile[];
  teams: Team[];
  onClose: () => void;
}) {
  const mutation = useAssignShiftMutation(context);
  const [staffId, setStaffId] = useState("");
  const [shiftId, setShiftId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [workDate, setWorkDate] = useState(() => uaeDateKey());
  const [assignmentError, setAssignmentError] = useState("");
  const eligibleTeams = useMemo(
    () => eligibleTeamsForStaff(staffId, staff, teams),
    [staff, staffId, teams],
  );
  useEffect(() => {
    if (teamId && !eligibleTeams.some((team) => team.id === teamId))
      setTeamId("");
  }, [eligibleTeams, teamId]);
  async function save() {
    setAssignmentError("");
    const payload = {
      staff_id: staffId,
      shift_id: shiftId,
      work_date: workDate,
      team_id: teamId || null,
    };
    try {
      await mutation.mutateAsync(payload);
      await successHaptic();
      onClose();
    } catch (error) {
      const message = domainErrorMessage(
        error,
        "The shift could not be assigned. Please try again.",
      );
      setAssignmentError(
        error instanceof ApiError && error.requestId
          ? `${message} Reference: ${error.requestId}`
          : message,
      );
      if (__DEV__)
        console.warn("[Trifecta Shift] assignment_failed", {
          endpoint: error instanceof ApiError ? error.endpoint : undefined,
          status: error instanceof ApiError ? error.status : undefined,
          code: error instanceof ApiError ? error.code : undefined,
          request_id: error instanceof ApiError ? error.requestId : undefined,
          request: payload,
        });
    }
  }
  if (!visible) return null;
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={uiStyles.content}
    >
      <View style={uiStyles.row}>
        <Text style={styles.sheetTitle}>{t("Assign shift")}</Text>
        <Pressable onPress={onClose}>
          <Text style={uiStyles.link}>{t("Back")}</Text>
        </Pressable>
      </View>
      <DatePickerField
        label={t("Date")}
        value={workDate}
        minimumDate={wallDate(uaeDateKey())}
        onChange={setWorkDate}
      />
      <Text style={uiStyles.label}>{t("STAFF")}</Text>
      {staff.map((item) => (
        <Pressable
          key={item.id}
          style={[
            styles.memberChoice,
            staffId === item.id ? styles.memberSelected : undefined,
          ]}
          onPress={() => {
            setStaffId(item.id);
            if (
              teamId &&
              !eligibleTeamsForStaff(item.id, staff, teams).some(
                (team) => team.id === teamId,
              )
            )
              setTeamId("");
          }}
        >
          <Text style={styles.cardTitle}>{item.display_name}</Text>
        </Pressable>
      ))}
      <Text style={uiStyles.label}>{t("SHIFT")}</Text>
      {shifts.map((item) => (
        <Pressable
          key={item.id}
          style={[
            styles.memberChoice,
            shiftId === item.id ? styles.memberSelected : undefined,
          ]}
          onPress={() => setShiftId(item.id)}
        >
          <Text style={styles.cardTitle}>
            {item.name} · {item.start_time.slice(0, 5)}–
            {item.end_time.slice(0, 5)}
          </Text>
        </Pressable>
      ))}
      <Text style={uiStyles.label}>{t("TEAM (OPTIONAL)")}</Text>
      <Pressable
        style={[
          styles.memberChoice,
          !teamId ? styles.memberSelected : undefined,
        ]}
        onPress={() => setTeamId("")}
      >
        <Text style={styles.cardTitle}>{t("No team")}</Text>
      </Pressable>
      {eligibleTeams.map((item) => (
        <Pressable
          key={item.id}
          style={[
            styles.memberChoice,
            teamId === item.id ? styles.memberSelected : undefined,
          ]}
          onPress={() => setTeamId(item.id)}
        >
          <Text style={styles.cardTitle}>{item.name}</Text>
        </Pressable>
      ))}
      <Text style={uiStyles.muted}>
        {staffId
          ? eligibleTeams.length
            ? t("Only teams this employee belongs to are shown.")
            : t("This employee is not an active member of a team. Assign without a team or update team membership first.")
          : t("Select an employee to see valid teams.")}
      </Text>
      {assignmentError ? (
        <Text style={uiStyles.error}>{assignmentError}</Text>
      ) : null}
      <AppButton
        title={mutation.isPending ? t("Assigning…") : t("Assign shift")}
        disabled={mutation.isPending || !staffId || !shiftId || !workDate}
        loading={mutation.isPending}
        onPress={() => void save()}
      />
      <AppButton title={t("Cancel")} tone="secondary" onPress={onClose} />
    </ScrollView>
  );
}
const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
const styles = StyleSheet.create({
  segment: {
    flexDirection: "row",
    padding: spacing.sm,
    backgroundColor: colors.surface,
    gap: spacing.xs,
  },
  segmentItem: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderRadius: radii.sm,
  },
  segmentActive: { backgroundColor: colors.secondary },
  segmentText: { color: colors.textSecondary, fontSize: 11, fontWeight: "800" },
  segmentTextActive: { color: colors.primary },
  cardTitle: { color: colors.text, fontSize: 18, fontWeight: "900" },
  live: { color: colors.primary, fontWeight: "800" },
  personRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.secondary,
    alignItems: "center",
    justifyContent: "center",
  },
  initials: { color: colors.primary, fontWeight: "900" },
  warning: { color: colors.warning, fontWeight: "800" },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
    marginTop: spacing.md,
  },
  actions: { flexDirection: "row", gap: spacing.sm },
  sheetTitle: { fontSize: 26, fontWeight: "900", color: colors.text },
  roleChoice: {
    flex: 1,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    alignItems: "center",
  },
  roleActive: {
    backgroundColor: colors.secondary,
    borderColor: colors.primary,
  },
  memberChoice: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
  },
  memberSelected: {
    backgroundColor: colors.secondary,
    borderColor: colors.primary,
  },
  check: { color: colors.primary, fontSize: 22, fontWeight: "900" },
});
