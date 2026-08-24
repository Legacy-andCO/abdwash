import { useEffect, useState } from "react";
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
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
  createStaff,
  createTeam,
  getAttendance,
  getCancellations,
  getLeave,
  getStaff,
  getTeam,
  getTeams,
  reviewCancellation,
  reviewLeave,
  setTemporaryPassword,
  updateStaff,
  updateTeamMembers,
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
} from "../lib";
import { domainErrorMessage } from "../errors/domainErrors";
import {
  useAssignShiftMutation,
  useAttendanceOverviewQuery,
  useCreateShiftMutation,
  useJobsQuery,
  useLeaveQuery,
  useReportQuery,
  useShiftAssignmentsQuery,
  useShiftsQuery,
  useStaffQuery,
  useTeamsQuery,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";

type Section = "teams" | "staff" | "shifts" | "attendance";
export function TeamScreen({ context }: { context: StaffContext }) {
  const [section, setSection] = useState<Section>("teams");
  return (
    <View style={{ flex: 1 }}>
      <View style={styles.segment}>
        {(["teams", "staff", "shifts", "attendance"] as const).map((item) => (
          <Pressable
            key={item}
            onPress={() => setSection(item)}
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
              {item[0].toUpperCase() + item.slice(1)}
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
  const items = teamsQuery.data ?? [];
  const [add, setAdd] = useState(false);
  const [detail, setDetail] = useState<TeamDetail | null>(null);
  async function open(item: Team) {
    try {
      setDetail(await getTeam(item.id));
    } catch (error) {
      Alert.alert(
        "Team unavailable",
        domainErrorMessage(error, "Please try again."),
      );
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title="Teams"
        subtitle="Scheduling capacity and live workload"
      />
      <AppButton
        title="Create team"
        tone="secondary"
        onPress={() => setAdd(true)}
      />
      {teamsQuery.isPending ? (
        <Skeleton />
      ) : teamsQuery.isError ? (
        <Text style={uiStyles.error}>
          {domainErrorMessage(teamsQuery.error, "Teams could not load.")}
        </Text>
      ) : items.length ? (
        items.map((item) => (
          <Pressable key={item.id} onPress={() => void open(item)}>
            <Card>
              <View style={uiStyles.row}>
                <View>
                  <Text style={styles.cardTitle}>{item.name}</Text>
                  <Text style={uiStyles.muted}>
                    {item.member_count} members · {item.jobs_today} jobs today
                  </Text>
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
              <Text style={uiStyles.link}>Manage members →</Text>
            </Card>
          </Pressable>
        ))
      ) : (
        <EmptyState
          title="No teams yet"
          body="Create the first mobile team to add booking capacity."
        />
      )}
      <SimpleCreate
        visible={add}
        title="Create team"
        label="TEAM NAME"
        placeholder="Mobile Team 2"
        onClose={() => setAdd(false)}
        onSave={async (name) => {
          await createTeam(name);
          await successHaptic();
          setAdd(false);
          await teamsQuery.refetch();
        }}
      />
      <TeamMembersSheet
        detail={detail}
        staff={(staffQuery.data ?? []).filter((member) => member.is_active)}
        onClose={() => setDetail(null)}
        onSaved={async () => {
          setDetail(null);
          await Promise.all([teamsQuery.refetch(), staffQuery.refetch()]);
        }}
      />
    </ScrollView>
  );
}

function StaffPane({ context }: { context: StaffContext }) {
  const staffQuery = useStaffQuery(context);
  const attendance = useAttendanceOverviewQuery(context);
  const jobs = useJobsQuery(context, {
    view: "today",
    scope: "all",
    date: new Date().toISOString().slice(0, 10),
    limit: 100,
  });
  const end = new Date();
  const start = new Date(end);
  start.setDate(end.getDate() - 29);
  const report = useReportQuery(
    context,
    start.toISOString().slice(0, 10),
    end.toISOString().slice(0, 10),
  );
  const items = staffQuery.data ?? [];
  const [add, setAdd] = useState(false);
  const [selected, setSelected] = useState<Profile | null>(null);
  const [editTarget, setEditTarget] = useState<Profile | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<Profile | null>(null);
  async function toggle(item: Profile) {
    try {
      await updateStaff(item.id, { is_active: !item.is_active });
      await staffQuery.refetch();
      await successHaptic();
    } catch (error) {
      Alert.alert(
        "Update failed",
        domainErrorMessage(error, "The account could not be changed."),
      );
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title="Staff"
        subtitle="Accounts, roles and team membership"
      />
      <AppButton title="Add employee" onPress={() => setAdd(true)} />
      {staffQuery.isPending ? (
        <Skeleton />
      ) : staffQuery.isError ? (
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
                {item.phone ?? "No phone"}
                {item.teams.length
                  ? ` · ${item.teams.map((team) => team.name).join(", ")}`
                  : ""}
              </Text>
              <Text style={uiStyles.link}>View attendance & performance →</Text>
            </Pressable>
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Edit"
                  tone="secondary"
                  onPress={() => setEditTarget(item)}
                />
              </View>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Temporary password"
                  tone="secondary"
                  onPress={() => setPasswordTarget(item)}
                />
              </View>
            </View>
            <AppButton
              title={item.is_active ? "Deactivate" : "Reactivate"}
              tone={item.is_active ? "danger" : "secondary"}
              onPress={() => void toggle(item)}
            />
          </Card>
        ))
      )}
      <AddStaffSheet
        visible={add}
        canCreateManager={context.role === "admin"}
        onClose={() => setAdd(false)}
        onCreated={async () => {
          setAdd(false);
          await staffQuery.refetch();
        }}
      />
      <EditStaffSheet
        profile={editTarget}
        onClose={() => setEditTarget(null)}
        onSaved={async () => {
          setEditTarget(null);
          await staffQuery.refetch();
        }}
      />
      <PasswordSheet
        profile={passwordTarget}
        onClose={() => setPasswordTarget(null)}
      />
      <StaffDetailSheet
        profile={selected}
        attendance={attendance.data?.find(
          (item) => item.staff_id === selected?.id,
        )}
        jobs={(jobs.data?.jobs ?? []).filter(
          (item) => item.assigned_staff_id === selected?.id,
        )}
        performance={report.data?.staff_performance.find(
          (item) => item.id === selected?.id,
        )}
        onClose={() => setSelected(null)}
      />
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
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title="Shifts"
        subtitle="Today · assigned work and reusable templates"
      />
      <View style={styles.actions}>
        <View style={{ flex: 1 }}>
          <AppButton
            title="Create shift"
            tone="secondary"
            onPress={() => setAdd(true)}
          />
        </View>
        <View style={{ flex: 1 }}>
          <AppButton title="Assign shift" onPress={() => setAssigning(true)} />
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
            <Text style={uiStyles.muted}>{item.team_name ?? "No team"}</Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No shifts assigned today" />
      )}
      {shifts.length ? (
        <Text style={uiStyles.muted}>
          {shifts.length} shift templates available
        </Text>
      ) : null}
      <CreateShiftSheet
        visible={add}
        context={context}
        onClose={() => setAdd(false)}
      />
      <ShiftAssignmentSheet
        visible={assigning}
        context={context}
        shifts={shifts}
        staff={staff}
        teams={teams}
        onClose={() => setAssigning(false)}
      />
    </ScrollView>
  );
}

function AttendancePane({ context }: { context: StaffContext }) {
  const attendance = useAttendanceOverviewQuery(context);
  const leaveQuery = useLeaveQuery(context, "pending");
  const items = attendance.data ?? [];
  const leave = leaveQuery.data ?? [];
  const [cancellations, setCancellations] = useState<Cancellation[]>([]);
  useEffect(() => {
    void getCancellations().then(setCancellations);
  }, []);
  async function decideLeave(item: Leave, decision: "approved" | "rejected") {
    try {
      await reviewLeave(item.id, decision);
      await Promise.all([leaveQuery.refetch(), attendance.refetch()]);
      await successHaptic();
    } catch (reason) {
      Alert.alert(
        "Decision not saved",
        domainErrorMessage(reason, "Please retry."),
      );
    }
  }
  async function decideCancellation(
    item: Cancellation,
    decision: "approved" | "rejected",
  ) {
    try {
      await reviewCancellation(item.id, decision);
      setCancellations((current) =>
        current.filter((value) => value.id !== item.id),
      );
      await successHaptic();
    } catch (error) {
      Alert.alert(
        "Decision not saved",
        domainErrorMessage(error, "Please retry."),
      );
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <ScreenTitle
        title="Attendance"
        subtitle="Working, late, clocked out, absent, off and approved leave"
      />
      {attendance.isPending ? (
        <Skeleton />
      ) : attendance.isError ? (
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
                    ? `${item.shift_name} · ${item.shift_start?.slice(0, 5)}–${item.shift_end?.slice(0, 5)}`
                    : "No shift today"}
                </Text>
              </View>
              <StatusChip value={item.status} />
            </View>
            {item.clock_in_at ? (
              <Text style={uiStyles.muted}>
                {new Date(item.clock_in_at).toLocaleTimeString([], {
                  hour: "numeric",
                  minute: "2-digit",
                })}{" "}
                →{" "}
                {item.clock_out_at
                  ? new Date(item.clock_out_at).toLocaleTimeString([], {
                      hour: "numeric",
                      minute: "2-digit",
                    })
                  : "Now"}
              </Text>
            ) : null}
            {item.late_minutes ? (
              <Text style={styles.warning}>{item.late_minutes} min late</Text>
            ) : null}
            {item.missed_shift ? (
              <Text style={styles.warning}>Missed shift</Text>
            ) : null}
          </Card>
        ))
      )}
      <Text style={styles.section}>PENDING LEAVE</Text>
      {leave.length ? (
        leave.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.staff_name}</Text>
            <Text style={uiStyles.body}>
              {item.start_date}
              {item.end_date !== item.start_date ? ` → ${item.end_date}` : ""}
            </Text>
            <Text style={uiStyles.muted}>{item.reason}</Text>
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Reject"
                  tone="danger"
                  onPress={() => void decideLeave(item, "rejected")}
                />
              </View>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Approve"
                  onPress={() => void decideLeave(item, "approved")}
                />
              </View>
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title="No pending leave requests" />
      )}
      <Text style={styles.section}>CANCELLATIONS</Text>
      {cancellations.length ? (
        cancellations.map((item) => (
          <Card key={item.id}>
            <Text style={styles.cardTitle}>{item.customer_name}</Text>
            <Text style={uiStyles.body}>
              {item.booking_reference} ·{" "}
              {new Date(item.scheduled_start).toLocaleString()}
            </Text>
            <Text style={uiStyles.muted}>
              {item.reason ?? "No reason provided"}
            </Text>
            <StatusChip value={item.payment_status} />
            <View style={styles.actions}>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Reject"
                  tone="danger"
                  onPress={() => void decideCancellation(item, "rejected")}
                />
              </View>
              <View style={{ flex: 1 }}>
                <AppButton
                  title="Approve"
                  onPress={() => void decideCancellation(item, "approved")}
                />
              </View>
            </View>
          </Card>
        ))
      ) : (
        <EmptyState title="No cancellation requests" />
      )}
    </ScrollView>
  );
}

function AddStaffSheet({
  visible,
  canCreateManager,
  onClose,
  onCreated,
}: {
  visible: boolean;
  canCreateManager: boolean;
  onClose: () => void;
  onCreated: (profile: Profile) => void;
}) {
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"employee" | "manager">("employee");
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      const profile = await createStaff({
        display_name: name,
        username,
        phone,
        role,
        temporary_password: password,
      });
      await successHaptic();
      onCreated(profile);
    } catch (reason) {
      Alert.alert(
        "Account not created",
        reason instanceof Error && reason.message === "USERNAME_TAKEN"
          ? "That username is already in use."
          : "Check the details and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.sheet}>
          <View style={uiStyles.row}>
            <Text style={styles.sheetTitle}>Add staff</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          {[
            ["FULL NAME", name, setName, "Mohammed Ali"],
            ["USERNAME", username, setUsername, "mohammed"],
            ["PHONE", phone, setPhone, "+971 50 123 4567"],
            [
              "TEMPORARY PASSWORD",
              password,
              setPassword,
              "At least 8 characters",
            ],
          ].map(([label, value, setter, placeholder]) => (
            <View key={label as string}>
              <Text style={uiStyles.label}>{label as string}</Text>
              <TextInput
                style={uiStyles.field}
                value={value as string}
                onChangeText={setter as (value: string) => void}
                placeholder={placeholder as string}
                secureTextEntry={label === "TEMPORARY PASSWORD"}
                autoCapitalize="none"
              />
            </View>
          ))}
          {canCreateManager ? (
            <View style={styles.actions}>
              <Pressable
                onPress={() => setRole("employee")}
                style={[
                  styles.roleChoice,
                  role === "employee" ? styles.roleActive : undefined,
                ]}
              >
                <Text>Employee</Text>
              </Pressable>
              <Pressable
                onPress={() => setRole("manager")}
                style={[
                  styles.roleChoice,
                  role === "manager" ? styles.roleActive : undefined,
                ]}
              >
                <Text>Manager</Text>
              </Pressable>
            </View>
          ) : null}
          <AppButton
            title="Create account"
            disabled={busy || !name || !username || password.length < 8}
            onPress={() => void save()}
          />
        </ScrollView>
      </View>
    </Modal>
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
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={uiStyles.row}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
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
            title="Save"
            disabled={busy || value.trim().length < 2}
            onPress={() => {
              setBusy(true);
              void onSave(value.trim())
                .catch(() => Alert.alert("Not saved", "Please try again."))
                .finally(() => setBusy(false));
            }}
          />
        </View>
      </View>
    </Modal>
  );
}
function TeamMembersSheet({
  detail,
  staff,
  onClose,
  onSaved,
}: {
  detail: TeamDetail | null;
  staff: Profile[];
  onClose: () => void;
  onSaved: (team: TeamDetail) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => {
    setSelected(detail?.members.map((member) => member.id) ?? []);
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
    const next = await updateTeamMembers(detail.id, selected);
    await successHaptic();
    onSaved(next);
  }
  return (
    <Modal
      visible={detail !== null}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView contentContainerStyle={styles.sheet}>
          <View style={uiStyles.row}>
            <Text style={styles.sheetTitle}>{detail?.name}</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          <Text style={uiStyles.muted}>
            {detail?.jobs_today ?? 0} jobs today
          </Text>
          {staff.map((member) => (
            <Pressable
              key={member.id}
              style={[
                styles.memberChoice,
                selected.includes(member.id)
                  ? styles.memberSelected
                  : undefined,
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
          <AppButton title="Save members" onPress={() => void save()} />
        </ScrollView>
      </View>
    </Modal>
  );
}
function EditStaffSheet({
  profile,
  onClose,
  onSaved,
}: {
  profile: Profile | null;
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
      await updateStaff(profile.id, {
        display_name: name.trim(),
        phone: phone.trim() || null,
      });
      await successHaptic();
      await onSaved();
    } catch (error) {
      Alert.alert(
        "Profile not saved",
        domainErrorMessage(error, "Check the staff details and try again."),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      visible={profile !== null}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.sheet}
        >
          <Text style={styles.sheetTitle}>Edit staff</Text>
          <Text style={uiStyles.label}>FULL NAME</Text>
          <TextInput
            style={uiStyles.field}
            value={name}
            onChangeText={setName}
          />
          <Text style={uiStyles.label}>PHONE</Text>
          <TextInput
            style={uiStyles.field}
            value={phone}
            onChangeText={setPhone}
            keyboardType="phone-pad"
          />
          <AppButton
            title={busy ? "Saving…" : "Save changes"}
            disabled={busy || name.trim().length < 2}
            onPress={() => void save()}
          />
          <AppButton title="Cancel" tone="secondary" onPress={onClose} />
        </ScrollView>
      </View>
    </Modal>
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
  return (
    <Modal
      visible={profile !== null}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView contentContainerStyle={styles.sheet}>
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.sheetTitle}>{profile?.display_name}</Text>
              <Text style={uiStyles.muted}>
                @{profile?.username} · {profile?.role}
              </Text>
            </View>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          <Text style={styles.section}>TEAMS</Text>
          <Text style={uiStyles.body}>
            {profile?.teams.length
              ? profile.teams.map((team) => team.name).join(", ")
              : "No team membership"}
          </Text>
          <Text style={styles.section}>TODAY'S ATTENDANCE</Text>
          {attendance ? (
            <Card>
              <StatusChip value={attendance.status} />
              <Text style={uiStyles.muted}>
                {attendance.worked_minutes} minutes worked ·{" "}
                {attendance.late_minutes} minutes late
              </Text>
            </Card>
          ) : (
            <EmptyState title="No attendance recorded" />
          )}
          <Text style={styles.section}>TODAY'S JOBS</Text>
          <Text style={styles.cardTitle}>{jobs.length}</Text>
          <Text style={styles.section}>LAST 30 DAYS</Text>
          {performance ? (
            <Card>
              <Text style={uiStyles.body}>
                {performance.jobs_completed} completed ·{" "}
                {performance.hours_worked.toFixed(1)} hours
              </Text>
              <Text style={uiStyles.muted}>
                Average wash {performance.average_wash_minutes} min ·{" "}
                {performance.late_arrivals} late arrivals
              </Text>
              <Text style={uiStyles.muted}>
                {performance.jobs_per_worked_hour.toFixed(2)} jobs per worked
                hour
              </Text>
            </Card>
          ) : (
            <EmptyState title="No performance data" />
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}
function PasswordSheet({
  profile,
  onClose,
}: {
  profile: Profile | null;
  onClose: () => void;
}) {
  const [password, setPassword] = useState("");
  async function save() {
    if (!profile) return;
    try {
      await setTemporaryPassword(profile.id, password);
      await successHaptic();
      setPassword("");
      onClose();
    } catch {
      Alert.alert("Password not changed", "Please try again.");
    }
  }
  return (
    <Modal
      visible={profile !== null}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.sheetTitle}>Temporary password</Text>
          <Text style={uiStyles.muted}>{profile?.display_name}</Text>
          <TextInput
            style={uiStyles.field}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="At least 8 characters"
          />
          <AppButton
            title="Set password"
            disabled={password.length < 8}
            onPress={() => void save()}
          />
          <AppButton title="Cancel" tone="secondary" onPress={onClose} />
        </View>
      </View>
    </Modal>
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
  const validTime = /^([01]\d|2[0-3]):[0-5]\d$/;
  const valid =
    name.trim().length >= 2 &&
    validTime.test(startTime) &&
    validTime.test(endTime) &&
    startTime < endTime;
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
        "Shift not created",
        domainErrorMessage(error, "Check the name and times, then try again."),
      );
    }
  }
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.sheet}
        >
          <Text style={styles.sheetTitle}>Create shift</Text>
          <Text style={uiStyles.label}>SHIFT NAME</Text>
          <TextInput
            accessibilityLabel="Shift name"
            style={uiStyles.field}
            value={name}
            onChangeText={setName}
            placeholder="Morning"
          />
          <Text style={uiStyles.label}>START</Text>
          <TextInput
            accessibilityLabel="Shift start time"
            style={uiStyles.field}
            value={startTime}
            onChangeText={setStartTime}
            placeholder="09:00"
            keyboardType="numbers-and-punctuation"
          />
          <Text style={uiStyles.label}>END</Text>
          <TextInput
            accessibilityLabel="Shift end time"
            style={uiStyles.field}
            value={endTime}
            onChangeText={setEndTime}
            placeholder="18:00"
            keyboardType="numbers-and-punctuation"
          />
          {name && !valid ? (
            <Text style={uiStyles.error}>
              Use valid same-day times; the end must be after the start.
            </Text>
          ) : null}
          <AppButton
            title={mutation.isPending ? "Creating…" : "Create shift"}
            disabled={mutation.isPending || !valid}
            onPress={() => void save()}
          />
          <AppButton title="Cancel" tone="secondary" onPress={onClose} />
        </ScrollView>
      </View>
    </Modal>
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
  const [workDate, setWorkDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  async function save() {
    try {
      await mutation.mutateAsync({
        staff_id: staffId,
        shift_id: shiftId,
        work_date: workDate,
        team_id: teamId || null,
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Shift not assigned",
        domainErrorMessage(error, "Review the staff, shift and date."),
      );
    }
  }
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={styles.sheet}
        >
          <Text style={styles.sheetTitle}>Assign shift</Text>
          <TextInput
            accessibilityLabel="Shift work date"
            style={uiStyles.field}
            value={workDate}
            onChangeText={setWorkDate}
            placeholder="YYYY-MM-DD"
          />
          <Text style={uiStyles.label}>STAFF</Text>
          {staff.map((item) => (
            <Pressable
              key={item.id}
              style={[
                styles.memberChoice,
                staffId === item.id ? styles.memberSelected : undefined,
              ]}
              onPress={() => setStaffId(item.id)}
            >
              <Text style={styles.cardTitle}>{item.display_name}</Text>
            </Pressable>
          ))}
          <Text style={uiStyles.label}>SHIFT</Text>
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
          <Text style={uiStyles.label}>TEAM (OPTIONAL)</Text>
          {teams.map((item) => (
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
          <AppButton
            title={mutation.isPending ? "Assigning…" : "Assign shift"}
            disabled={mutation.isPending || !staffId || !shiftId || !workDate}
            onPress={() => void save()}
          />
          <AppButton title="Cancel" tone="secondary" onPress={onClose} />
        </ScrollView>
      </View>
    </Modal>
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
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(10,30,26,0.38)",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    padding: spacing.xl,
    gap: spacing.md,
  },
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
