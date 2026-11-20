import { AttendanceHistory } from "../components/AttendanceHistory";
import { t } from "../i18n";
import { Alert } from "../alert";
import Constants from "expo-constants";
import { useState } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { signOutFromStaffApp } from "../authSignOut";
import { DatePickerField, fromIsoDate } from "../components/pickers";
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
import { validatePasswordConfirmation } from "../forms/password";
import { successHaptic } from "../haptics";
import type { StaffContext } from "../lib";
import {
  useLeaveQuery,
  useProfileQuery,
  useRequestLeaveMutation,
  useUpdateProfileMutation,
} from "../queries/operations";
import { colors, spacing } from "../theme";
import { uaeDateKey, wallDate } from "../time/uaeTime";

export function ProfileScreen({ context }: { context: StaffContext }) {
  const profileQuery = useProfileQuery(context);
  const leaveQuery = useLeaveQuery(context);
  const profileMutation = useUpdateProfileMutation(context);
  const leaveMutation = useRequestLeaveMutation(context);
  const profile = profileQuery.data;
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [startDate, setStartDate] = useState(() => uaeDateKey());
  const [endDate, setEndDate] = useState(() => uaeDateKey());
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
      });
      setEditing(false);
      await successHaptic();
    } catch (error) {
      Alert.alert(
        t("Profile not saved"),
        domainErrorMessage(error, "Check the details and try again."),
      );
    }
  }
  async function changePassword() {
    const validation = validatePasswordConfirmation(
      newPassword,
      passwordConfirmation,
    );
    if (validation) {
      Alert.alert(t("Password not changed"), validation);
      return;
    }
    try {
      await profileMutation.mutateAsync({ password: newPassword });
      setNewPassword("");
      setPasswordConfirmation("");
      setChangingPassword(false);
      await successHaptic();
      Alert.alert(t("Password changed successfully."));
    } catch (error) {
      Alert.alert(
        t("Password not changed"),
        domainErrorMessage(error, "Choose a valid password and try again."),
      );
    }
  }
  async function addLeave() {
    try {
      await leaveMutation.mutateAsync({
        start_date: startDate,
        end_date: endDate,
        reason,
      });
      const current = uaeDateKey();
      setStartDate(current);
      setEndDate(current);
      setReason("");
      await successHaptic();
    } catch (error) {
      Alert.alert(
        t("Request not sent"),
        domainErrorMessage(error, "Use a valid date and try again."),
      );
    }
  }
  async function refresh() {
    await Promise.all([
      profileQuery.refetch(),
      leaveQuery.refetch(),
    ]);
  }
  if (profileQuery.isPending)
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <Skeleton rows={5} />
      </ScrollView>
    );
  if (profileQuery.isError && !profile)
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <EmptyState
          title={t("Profile unavailable")}
          body={domainErrorMessage(
            profileQuery.error,
            "We couldn't load your profile.",
          )}
          action={
            <AppButton
              title={t("Try again")}
              onPress={() => void profileQuery.refetch()}
            />
          }
        />
      </ScrollView>
    );
  if (!profile) return null;
  const leave = leaveQuery.data ?? [];
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      refreshControl={
        <RefreshControl
          refreshing={
            profileQuery.isRefetching ||
            leaveQuery.isRefetching
          }
          onRefresh={() => void refresh()}
        />
      }
      contentContainerStyle={uiStyles.content}
    >
      <AttendanceHistory context={context} />
      <View style={styles.identity}>
        <View style={styles.avatar}>
          <Text style={styles.initials}>{initials(profile.display_name)}</Text>
        </View>
        <ScreenTitle
          title={profile.display_name}
          subtitle={t("@{p0}", { p0: profile.username })}
        />
        <StatusChip value={profile.role} />
        <Text style={uiStyles.muted}>
          {profile.teams.map((team) => team.name).join(" · ") ||
            t("No team assigned")}
        </Text>
      </View>
      {profileQuery.error ? (
        <Text style={styles.offline}>
          {" " + t("Offline · profile updated") + ""}{" "}
          {new Date(profileQuery.dataUpdatedAt).toLocaleTimeString()}
        </Text>
      ) : null}
      <Card>
        {editing ? (
          <>
            <Text style={uiStyles.label}>{t("DISPLAY NAME")}</Text>
            <TextInput
              accessibilityLabel={t("Display name")}
              style={uiStyles.field}
              value={name}
              onChangeText={setName}
            />
            <Text style={uiStyles.label}>{t("PHONE")}</Text>
            <TextInput
              accessibilityLabel={t("Phone")}
              style={uiStyles.field}
              value={phone}
              onChangeText={setPhone}
              keyboardType="phone-pad"
            />
            <AppButton
              title={profileMutation.isPending ? t("Saving…") : t("Save profile")}
              disabled={profileMutation.isPending}
              loading={profileMutation.isPending}
              onPress={() => void save()}
            />
            <AppButton
              title={t("Cancel")}
              tone="secondary"
              onPress={() => setEditing(false)}
            />
          </>
        ) : (
          <>
            <Text style={uiStyles.label}>{t("PHONE")}</Text>
            <Text style={styles.value}>{profile.phone ?? t("Not added")}</Text>
            <Text style={uiStyles.label}>{t("ACCOUNT STATUS")}</Text>
            <Text style={styles.value}>
              {profile.is_active ? t("Active") : t("Inactive")}
            </Text>
            <AppButton
              title={t("Edit profile")}
              tone="secondary"
              onPress={beginEdit}
            />
          </>
        )}
      </Card>
      <Card>
        <Text style={styles.sectionTitle}>{t("PASSWORD")}</Text>
        {changingPassword ? (
          <>
            <TextInput
              accessibilityLabel={t("New password")}
              autoCapitalize="none"
              style={uiStyles.field}
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder={t("New password")}
              secureTextEntry
            />
            <TextInput
              accessibilityLabel={t("Confirm new password")}
              autoCapitalize="none"
              style={uiStyles.field}
              value={passwordConfirmation}
              onChangeText={setPasswordConfirmation}
              placeholder={t("Confirm new password")}
              secureTextEntry
            />
            <AppButton
              title={profileMutation.isPending ? t("Updating…") : t("Update password")}
              disabled={profileMutation.isPending}
              loading={profileMutation.isPending}
              onPress={() => void changePassword()}
            />
            <AppButton
              title={t("Cancel")}
              tone="secondary"
              onPress={() => {
                setNewPassword("");
                setPasswordConfirmation("");
                setChangingPassword(false);
              }}
            />
          </>
        ) : (
          <AppButton
            title={t("Change password")}
            tone="secondary"
            onPress={() => setChangingPassword(true)}
          />
        )}
      </Card>
      <Text style={styles.section}>{t("TIME OFF")}</Text>
      <Card>
        <Text style={uiStyles.label}>{t("REQUEST A DAY OFF")}</Text>
        <DatePickerField
          label={t("From")}
          value={startDate}
          minimumDate={wallDate(uaeDateKey())}
          onChange={(value) => {
            setStartDate(value);
            if (endDate < value) setEndDate(value);
          }}
        />
        <DatePickerField
          label={t("To")}
          value={endDate}
          minimumDate={fromIsoDate(startDate)}
          onChange={setEndDate}
        />
        <TextInput
          accessibilityLabel={t("Leave reason")}
          style={[uiStyles.field, styles.reason]}
          value={reason}
          onChangeText={setReason}
          placeholder={t("Reason")}
          multiline
        />
        <AppButton
          title={leaveMutation.isPending ? t("Requesting…") : t("Request day off")}
          disabled={
            leaveMutation.isPending || endDate < startDate || reason.length < 2
          }
          loading={leaveMutation.isPending}
          onPress={() => void addLeave()}
        />
      </Card>
      {leave.length ? (
        leave.slice(0, 5).map((item) => (
          <Card key={item.id}>
            <View style={uiStyles.row}>
              <Text style={styles.value}>
                {item.start_date}
                {item.end_date !== item.start_date ? t("–{p0}", { p0: item.end_date }) : ""}
              </Text>
              <StatusChip value={item.status} />
            </View>
            <Text style={uiStyles.muted}>{item.reason}</Text>
          </Card>
        ))
      ) : (
        <EmptyState title={t("No time-off requests")} />
      )}
      <Text style={styles.version}>
        {" " + t("Trifecta Operations") + " "}{Constants.expoConfig?.version ?? "1.0.0"}
      </Text>
      <AppButton
        title={t("Sign out")}
        tone="danger"
        onPress={() => void signOutFromStaffApp()}
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
  sectionTitle: {
    color: colors.textSecondary,
    fontWeight: "900",
    fontSize: 11,
    letterSpacing: 1.2,
  },
  version: {
    textAlign: "center",
    color: colors.textSecondary,
    marginTop: spacing.lg,
  },
  reason: { minHeight: 80 },
  offline: {
    color: colors.warning,
    backgroundColor: colors.warningSurface,
    padding: spacing.md,
  },
});
