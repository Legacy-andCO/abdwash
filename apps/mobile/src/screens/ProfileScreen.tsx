import Constants from "expo-constants";
import { useState } from "react";
import {
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { clearOperationalCache } from "../cache/queryClient";
import {
  AppButton,
  Card,
  EmptyState,
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import { successHaptic } from "../haptics";
import { supabase, type StaffContext } from "../lib";
import {
  useAttendanceHistoryQuery,
  useLeaveQuery,
  useProfileQuery,
  useRequestLeaveMutation,
  useUpdateProfileMutation,
} from "../queries/operations";
import { colors, spacing } from "../theme";

export function ProfileScreen({ context }: { context: StaffContext }) {
  const end = new Date().toISOString().slice(0, 10);
  const start = new Date(Date.now() - 30 * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const profileQuery = useProfileQuery(context);
  const attendanceQuery = useAttendanceHistoryQuery(context, start, end);
  const leaveQuery = useLeaveQuery(context);
  const profileMutation = useUpdateProfileMutation(context);
  const leaveMutation = useRequestLeaveMutation(context);
  const profile = profileQuery.data;
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [startDate, setStartDate] = useState("");
  const [reason, setReason] = useState("");
  function beginEdit() {
    if (!profile) return;
    setName(profile.display_name);
    setPhone(profile.phone ?? "");
    setEditing(true);
  }
  async function save() {
    try {
      await profileMutation.mutateAsync({
        display_name: name,
        phone,
        ...(password ? { password } : {}),
      });
      setPassword("");
      setEditing(false);
      await successHaptic();
    } catch (error) {
      Alert.alert(
        "Profile not saved",
        domainErrorMessage(error, "Check the details and try again."),
      );
    }
  }
  async function addLeave() {
    try {
      await leaveMutation.mutateAsync({
        start_date: startDate,
        end_date: startDate,
        reason,
      });
      setStartDate("");
      setReason("");
      await successHaptic();
    } catch (error) {
      Alert.alert(
        "Request not sent",
        domainErrorMessage(error, "Use a valid date and try again."),
      );
    }
  }
  async function refresh() {
    await Promise.all([
      profileQuery.refetch(),
      attendanceQuery.refetch(),
      leaveQuery.refetch(),
    ]);
  }
  if (profileQuery.isPending || !profile)
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <Skeleton rows={5} />
      </ScrollView>
    );
  const attendance = attendanceQuery.data?.items ?? [];
  const leave = leaveQuery.data ?? [];
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={
            profileQuery.isRefetching ||
            attendanceQuery.isRefetching ||
            leaveQuery.isRefetching
          }
          onRefresh={() => void refresh()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <View style={styles.identity}>
        <View style={styles.avatar}>
          <Text style={styles.initials}>{initials(profile.display_name)}</Text>
        </View>
        <ScreenTitle
          title={profile.display_name}
          subtitle={`@${profile.username}`}
        />
        <StatusChip value={profile.role} />
        <Text style={uiStyles.muted}>
          {profile.teams.map((team) => team.name).join(" · ") ||
            "No team assigned"}
        </Text>
      </View>
      {profileQuery.error ? (
        <Text style={styles.offline}>
          Offline · profile updated {new Date(profileQuery.dataUpdatedAt).toLocaleTimeString()}
        </Text>
      ) : null}
      <Card>
        {editing ? (
          <>
            <Text style={uiStyles.label}>DISPLAY NAME</Text>
            <TextInput
              accessibilityLabel="Display name"
              style={uiStyles.field}
              value={name}
              onChangeText={setName}
            />
            <Text style={uiStyles.label}>PHONE</Text>
            <TextInput
              accessibilityLabel="Phone"
              style={uiStyles.field}
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
            />
            <Text style={uiStyles.label}>NEW PASSWORD (OPTIONAL)</Text>
            <TextInput
              accessibilityLabel="New password"
              style={uiStyles.field}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />
            <AppButton
              title={profileMutation.isPending ? "Saving…" : "Save profile"}
              disabled={profileMutation.isPending}
              onPress={() => void save()}
            />
            <AppButton
              title="Cancel"
              tone="secondary"
              onPress={() => setEditing(false)}
            />
          </>
        ) : (
          <>
            <Text style={uiStyles.label}>PHONE</Text>
            <Text style={styles.value}>{profile.phone ?? "Not added"}</Text>
            <Text style={uiStyles.label}>ACCOUNT STATUS</Text>
            <Text style={styles.value}>
              {profile.is_active ? "Active" : "Inactive"}
            </Text>
            <AppButton
              title="Edit profile"
              tone="secondary"
              onPress={beginEdit}
            />
          </>
        )}
      </Card>
      <Text style={styles.section}>TIME OFF</Text>
      <Card>
        <Text style={uiStyles.label}>REQUEST A DAY OFF</Text>
        <TextInput
          accessibilityLabel="Leave date"
          style={uiStyles.field}
          value={startDate}
          onChangeText={setStartDate}
          placeholder="YYYY-MM-DD"
        />
        <TextInput
          accessibilityLabel="Leave reason"
          style={[uiStyles.field, styles.reason]}
          value={reason}
          onChangeText={setReason}
          placeholder="Reason"
          multiline
        />
        <AppButton
          title={leaveMutation.isPending ? "Requesting…" : "Request day off"}
          disabled={leaveMutation.isPending || !startDate || reason.length < 2}
          onPress={() => void addLeave()}
        />
      </Card>
      {leave.length ? (
        leave.slice(0, 5).map((item) => (
          <Card key={item.id}>
            <View style={uiStyles.row}>
              <Text style={styles.value}>
                {item.start_date}
                {item.end_date !== item.start_date ? `–${item.end_date}` : ""}
              </Text>
              <StatusChip value={item.status} />
            </View>
            <Text style={uiStyles.muted}>{item.reason}</Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No time-off requests" />
      )}
      <Text style={styles.section}>ATTENDANCE · LAST 30 DAYS</Text>
      {attendance.length ? (
        attendance.slice(0, 10).map((item) => (
          <Card key={item.id}>
            <View style={uiStyles.row}>
              <Text style={styles.value}>
                {new Date(item.clock_in_at).toLocaleDateString()}
              </Text>
              <StatusChip value={item.status} />
            </View>
            <Text style={uiStyles.muted}>
              {Math.floor(item.worked_minutes / 60)}h {item.worked_minutes % 60}
              m worked
            </Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No attendance history yet" />
      )}
      <Text style={styles.version}>
        AbdWash Operations {Constants.expoConfig?.version ?? "1.0.0"}
      </Text>
      <AppButton
        title="Sign out"
        tone="danger"
        onPress={() =>
          void (async () => {
            await clearOperationalCache();
            await supabase.auth.signOut();
          })()
        }
      />
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
  identity: {
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.lg,
  },
  avatar: {
    width: 82,
    height: 82,
    borderRadius: 41,
    backgroundColor: colors.secondary,
    alignItems: "center",
    justifyContent: "center",
  },
  initials: { fontSize: 28, fontWeight: "900", color: colors.primary },
  value: { color: colors.text, fontSize: 17, fontWeight: "800" },
  section: {
    color: colors.textSecondary,
    fontWeight: "900",
    fontSize: 11,
    letterSpacing: 1.2,
    marginTop: spacing.md,
  },
  version: {
    textAlign: "center",
    color: colors.textSecondary,
    marginTop: spacing.lg,
  },
  reason: { minHeight: 80 },
  offline: {
    color: colors.warning,
    backgroundColor: "#FFF1D7",
    padding: spacing.md,
  },
});
