import * as Location from "expo-location";
import { useMemo, useState } from "react";
import {
  Alert,
  Linking,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { capabilities } from "../capabilities";
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
import type {
  AvailabilitySlot,
  Job,
  JobFilters,
  Profile,
  StaffContext,
  Team,
} from "../lib";
import { availabilityOptions, isIsoBookingDate } from "../operations";
import {
  useAssignJobMutation,
  useAvailabilityQuery,
  useJobActionMutation,
  useJobQuery,
  useJobsQuery,
  useRescheduleMutation,
  useStaffQuery,
  useTeamsQuery,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";

type JobView = "today" | "upcoming" | "history" | "unassigned" | "all";
const today = () => new Date().toISOString().slice(0, 10);
const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

export function JobsScreen({ context }: { context: StaffContext }) {
  const canManage = capabilities(context.role).canViewAllJobs;
  const views: JobView[] = canManage
    ? ["today", "upcoming", "unassigned", "history", "all"]
    : ["today", "upcoming", "history"];
  const [view, setView] = useState<JobView>("today");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Job | null>(null);
  const filters = useMemo<JobFilters>(
    () => ({
      view,
      scope: canManage ? "all" : "my",
      ...(view === "today" ? { date: today() } : {}),
      offset,
      limit: 50,
    }),
    [canManage, offset, view],
  );
  const query = useJobsQuery(context, filters);
  const jobs = query.data?.jobs ?? [];
  if (selected)
    return (
      <JobDetail
        context={context}
        initial={selected}
        onBack={() => setSelected(null)}
      />
    );
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
      <ScreenTitle title="Jobs" subtitle="Server-filtered operational work" />
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.segment}
      >
        {views.map((item) => (
          <Pressable
            accessibilityRole="tab"
            accessibilityState={{ selected: view === item }}
            key={item}
            style={[
              styles.segmentItem,
              view === item ? styles.segmentActive : undefined,
            ]}
            onPress={() => {
              setView(item);
              setOffset(0);
            }}
          >
            <Text style={styles.segmentText}>{label(item)}</Text>
          </Pressable>
        ))}
      </ScrollView>
      {query.isError && jobs.length ? (
        <Text style={styles.offline}>
          Offline · last updated{" "}
          {new Date(query.dataUpdatedAt).toLocaleTimeString()}
        </Text>
      ) : null}
      {query.isPending ? (
        <Skeleton rows={4} />
      ) : query.isError && !jobs.length ? (
        <EmptyState
          title="Jobs unavailable"
          body={domainErrorMessage(query.error, "We couldn't load jobs.")}
          action={
            <AppButton title="Try again" onPress={() => void query.refetch()} />
          }
        />
      ) : jobs.length ? (
        <>
          {jobs.map((job) => (
            <Pressable
              accessibilityRole="button"
              key={job.id}
              onPress={() => setSelected(job)}
            >
              <JobCard job={job} />
            </Pressable>
          ))}
          <View style={styles.actions}>
            <View style={styles.action}>
              <AppButton
                title="Previous"
                tone="secondary"
                disabled={offset === 0}
                onPress={() => setOffset(Math.max(0, offset - 50))}
              />
            </View>
            <View style={styles.action}>
              <AppButton
                title="Next"
                tone="secondary"
                disabled={query.data?.next_offset === null}
                onPress={() => setOffset(query.data?.next_offset ?? offset)}
              />
            </View>
          </View>
        </>
      ) : (
        <EmptyState
          title={`No ${view} jobs`}
          body="Pull to refresh or choose another view."
        />
      )}
    </ScrollView>
  );
}

function JobCard({ job }: { job: Job }) {
  return (
    <Card>
      <View style={uiStyles.row}>
        <Text style={styles.time}>{formatTime(job.scheduled_start)}</Text>
        <StatusChip value={job.status} />
      </View>
      <Text style={styles.vehicle}>
        {job.vehicles[0]
          ? `${job.vehicles[0].make} ${job.vehicles[0].model}`
          : job.customer_name}
      </Text>
      <Text style={uiStyles.body}>
        {job.customer_name} · {job.vehicles[0]?.service_name}
      </Text>
      <Text numberOfLines={2} style={uiStyles.muted}>
        {job.written_address}
      </Text>
      <View style={uiStyles.row}>
        <Text style={styles.assignment}>
          {job.assigned_team_name ?? job.assigned_staff_name ?? "UNASSIGNED"}
        </Text>
        <StatusChip value={job.payment_status} />
      </View>
    </Card>
  );
}

function JobDetail({
  context,
  initial,
  onBack,
}: {
  context: StaffContext;
  initial: Job;
  onBack: () => void;
}) {
  const query = useJobQuery(context, initial.id, initial);
  const job = query.data ?? initial;
  const actionMutation = useJobActionMutation(context);
  const [assignment, setAssignment] = useState(false);
  const [reschedule, setReschedule] = useState(false);
  async function action(
    name: "start-trip" | "start" | "complete" | "cash-payment",
  ) {
    let body: object = {
      client_event_id: crypto.randomUUID(),
      client_timestamp: new Date().toISOString(),
    };
    try {
      if (name === "start-trip") {
        const permission = await Location.requestForegroundPermissionsAsync();
        if (!permission.granted) {
          Alert.alert(
            "Location needed",
            "Location is used once to calculate the customer ETA.",
          );
          return;
        }
        const origin = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        body = {
          ...body,
          origin: {
            latitude: origin.coords.latitude,
            longitude: origin.coords.longitude,
          },
        };
      }
      await actionMutation.mutateAsync({ jobId: job.id, action: name, body });
      await successHaptic();
    } catch (error) {
      Alert.alert(
        "Action not completed",
        domainErrorMessage(
          error,
          "The server did not confirm this action. Retry safely.",
        ),
      );
    }
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <Pressable onPress={onBack}>
        <Text style={uiStyles.link}>← All jobs</Text>
      </Pressable>
      {query.isError ? (
        <Text style={styles.offline}>
          Offline · showing details updated{" "}
          {new Date(query.dataUpdatedAt).toLocaleTimeString()}
        </Text>
      ) : null}
      <View style={uiStyles.row}>
        <View>
          <Text style={styles.detailTime}>
            {formatTime(job.scheduled_start)}–{formatTime(job.scheduled_end)}
          </Text>
          {job.estimated_arrival_at ? (
            <Text style={styles.eta}>
              ETA {formatTime(job.estimated_arrival_at)}
            </Text>
          ) : null}
        </View>
        <StatusChip value={job.status} />
      </View>
      <Text style={styles.heroVehicle}>
        {job.vehicles[0]
          ? `${job.vehicles[0].make} ${job.vehicles[0].model}`
          : job.booking_reference}
      </Text>
      <Text style={uiStyles.muted}>{job.vehicles[0]?.service_name}</Text>
      <View style={styles.actions}>
        <View style={styles.action}>
          <AppButton
            title="Navigate"
            tone="secondary"
            onPress={() => void Linking.openURL(job.location_url)}
          />
        </View>
        <View style={styles.action}>
          <AppButton
            title="Call"
            tone="secondary"
            onPress={() => void Linking.openURL(`tel:${job.customer_phone}`)}
          />
        </View>
      </View>
      {capabilities(context.role).canAssignJobs ? (
        <Card>
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.sectionTitle}>ASSIGNMENT</Text>
              <Text style={uiStyles.muted}>
                {job.assigned_team_name ??
                  job.assigned_staff_name ??
                  "Unassigned"}
              </Text>
            </View>
            <Pressable onPress={() => setAssignment(true)}>
              <Text style={uiStyles.link}>Change</Text>
            </Pressable>
          </View>
          <AppButton
            title="Reschedule appointment"
            tone="secondary"
            onPress={() => setReschedule(true)}
          />
        </Card>
      ) : null}
      <Card>
        <Text style={styles.sectionTitle}>CUSTOMER</Text>
        <Text style={styles.vehicle}>{job.customer_name}</Text>
        <Text style={uiStyles.body}>{job.customer_phone}</Text>
      </Card>
      <Card>
        <Text style={styles.sectionTitle}>LOCATION</Text>
        <Text style={uiStyles.body}>{job.written_address}</Text>
        {job.location_instructions ? (
          <Text style={uiStyles.muted}>{job.location_instructions}</Text>
        ) : null}
      </Card>
      <Card>
        <Text style={styles.sectionTitle}>VEHICLES & SERVICES</Text>
        {job.vehicles.map((vehicle, index) => (
          <View key={`${vehicle.make}-${index}`}>
            <Text style={styles.vehicle}>
              {vehicle.make} {vehicle.model}
            </Text>
            <Text style={uiStyles.muted}>
              {vehicle.service_name} · {vehicle.plate_number ?? "No plate"}
            </Text>
          </View>
        ))}
      </Card>
      <Card>
        <Text style={styles.sectionTitle}>PAYMENT</Text>
        <View style={uiStyles.row}>
          <Text style={styles.vehicle}>
            {job.currency_code} {(job.total_amount_minor / 100).toFixed(2)}
          </Text>
          <StatusChip value={job.payment_status} />
        </View>
      </Card>
      <Card>
        <Text style={styles.sectionTitle}>TIMELINE</Text>
        {query.isFetching && !job.timeline.length ? (
          <Skeleton rows={3} />
        ) : job.timeline.length ? (
          job.timeline.map((event) => (
            <View key={event.id} style={styles.timelineRow}>
              <Text style={styles.timelineTime}>
                {formatTime(event.occurred_at)}
              </Text>
              <View style={styles.timelineBody}>
                <Text style={styles.vehicle}>{event.event}</Text>
                {event.actor ? (
                  <Text style={uiStyles.muted}>{event.actor}</Text>
                ) : null}
                {event.detail ? (
                  <Text style={uiStyles.muted}>{event.detail}</Text>
                ) : null}
              </View>
            </View>
          ))
        ) : (
          <Text style={uiStyles.muted}>No recorded events yet.</Text>
        )}
      </Card>
      {job.status === "assigned" ? (
        <AppButton
          title="Start trip"
          disabled={actionMutation.isPending}
          onPress={() => void action("start-trip")}
        />
      ) : job.status === "en_route" ? (
        <AppButton
          title="Start wash"
          disabled={actionMutation.isPending}
          onPress={() => void action("start")}
        />
      ) : job.status === "in_progress" ? (
        <AppButton
          title="Complete wash"
          disabled={actionMutation.isPending}
          onPress={() => void action("complete")}
        />
      ) : job.status === "completed" && job.payment_status !== "paid" ? (
        <AppButton
          title="Record cash received"
          disabled={actionMutation.isPending}
          onPress={() =>
            Alert.alert(
              "Confirm cash",
              `Record ${job.currency_code} ${(job.total_amount_minor / 100).toFixed(2)} received?`,
              [
                { text: "Cancel" },
                { text: "Confirm", onPress: () => void action("cash-payment") },
              ],
            )
          }
        />
      ) : null}
      {capabilities(context.role).canAssignJobs ? (
        <>
          <AssignmentSheet
            context={context}
            visible={assignment}
            job={job}
            onClose={() => setAssignment(false)}
          />
          <RescheduleSheet
            context={context}
            visible={reschedule}
            job={job}
            onClose={() => setReschedule(false)}
          />
        </>
      ) : null}
    </ScrollView>
  );
}

function AssignmentSheet({
  context,
  visible,
  job,
  onClose,
}: {
  context: StaffContext;
  visible: boolean;
  job: Job;
  onClose: () => void;
}) {
  const teamsQuery = useTeamsQuery(context);
  const staffQuery = useStaffQuery(context);
  const mutation = useAssignJobMutation(context);
  const [target, setTarget] = useState<{ team_id?: string; staff_id?: string }>(
    {},
  );
  const teams = (teamsQuery.data ?? []).filter((item: Team) => item.is_active);
  const staff = (staffQuery.data ?? []).filter(
    (item: Profile) => item.is_active,
  );
  async function save() {
    try {
      await mutation.mutateAsync({
        jobId: job.id,
        body: {
          ...target,
          confirm_active_reassignment: ["en_route", "in_progress"].includes(
            job.status,
          ),
          client_event_id: crypto.randomUUID(),
          client_timestamp: new Date().toISOString(),
        },
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Assignment not completed",
        domainErrorMessage(error, "Review the assignment and try again."),
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
          <View style={uiStyles.row}>
            <Text style={styles.heroVehicle}>Assign job</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          {teamsQuery.isPending || staffQuery.isPending ? (
            <Skeleton rows={3} />
          ) : null}
          <Text style={styles.sectionTitle}>TEAMS</Text>
          {teams.map((item) => (
            <Choice
              key={item.id}
              selected={target.team_id === item.id}
              title={item.name}
              detail={`${item.member_count} members · ${item.jobs_today} jobs today`}
              onPress={() => setTarget({ team_id: item.id })}
            />
          ))}
          <Text style={styles.sectionTitle}>INDIVIDUALS</Text>
          {staff.map((item) => (
            <Choice
              key={item.id}
              selected={target.staff_id === item.id}
              title={item.display_name}
              detail={`@${item.username}`}
              onPress={() => setTarget({ staff_id: item.id })}
            />
          ))}
          <AppButton
            title={mutation.isPending ? "Assigning…" : "Assign"}
            disabled={
              mutation.isPending || (!target.staff_id && !target.team_id)
            }
            onPress={() => void save()}
          />
        </ScrollView>
      </View>
    </Modal>
  );
}

function RescheduleSheet({
  context,
  visible,
  job,
  onClose,
}: {
  context: StaffContext;
  visible: boolean;
  job: Job;
  onClose: () => void;
}) {
  const [selectedDay, setSelectedDay] = useState("");
  const [selection, setSelection] = useState<{
    slot: AvailabilitySlot;
    resourceId: string;
  } | null>(null);
  const vehicleCount = Math.max(1, job.vehicles.length);
  const validDay = isIsoBookingDate(selectedDay);
  const availability = useAvailabilityQuery(
    job.booking_id,
    selectedDay,
    vehicleCount,
    visible && validDay,
  );
  const mutation = useRescheduleMutation(context, job);
  const options = availabilityOptions(availability.data?.slots ?? []);
  function changeDay(value: string) {
    setSelectedDay(value);
    setSelection(null);
  }
  async function confirm() {
    if (!selection) return;
    try {
      await mutation.mutateAsync({
        selectedDay,
        startTime: selection.slot.time,
        resourceId: selection.resourceId,
      });
      await successHaptic();
      onClose();
    } catch (error) {
      Alert.alert(
        "Reschedule not completed",
        domainErrorMessage(
          error,
          "The appointment may have changed. Refresh times and retry.",
        ),
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
          <View style={uiStyles.row}>
            <Text style={styles.heroVehicle}>Reschedule</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          <Text style={uiStyles.muted}>
            Current · {new Date(job.scheduled_start).toLocaleString()}
          </Text>
          <Text style={uiStyles.label}>NEW DATE</Text>
          <TextInput
            accessibilityLabel="New appointment date"
            style={uiStyles.field}
            value={selectedDay}
            onChangeText={changeDay}
            placeholder="YYYY-MM-DD"
            autoCapitalize="none"
          />
          {!selectedDay ? (
            <EmptyState title="Choose a date to see times" />
          ) : !validDay ? (
            <Text accessibilityRole="alert" style={uiStyles.error}>
              Use the YYYY-MM-DD date format.
            </Text>
          ) : availability.isPending || availability.isFetching ? (
            <>
              <Text style={uiStyles.muted}>Loading available times…</Text>
              <Skeleton rows={3} />
            </>
          ) : availability.isError ? (
            <EmptyState
              title="We couldn't load available times"
              body="Check your connection and try again."
              action={
                <AppButton
                  title="Try again"
                  onPress={() => void availability.refetch()}
                />
              }
            />
          ) : options.length === 0 ? (
            <EmptyState
              title="No available appointments on this date"
              body="Choose another day."
            />
          ) : (
            <>
              <Text style={styles.sectionTitle}>AVAILABLE TIMES</Text>
              {options.map(({ slot, resource }) => (
                <Choice
                  key={`${slot.starts_at}:${resource.resource_id}`}
                  selected={
                    selection?.slot.starts_at === slot.starts_at &&
                    selection.resourceId === resource.resource_id
                  }
                  title={`${formatTime(slot.starts_at)}–${formatTime(slot.ends_at)}`}
                  detail={resource.resource_name}
                  onPress={() =>
                    setSelection({ slot, resourceId: resource.resource_id })
                  }
                />
              ))}
              <AppButton
                title={
                  mutation.isPending ? "Rescheduling…" : "Confirm reschedule"
                }
                disabled={mutation.isPending || !selection}
                onPress={() => void confirm()}
              />
            </>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

function Choice({
  selected,
  title,
  detail,
  onPress,
}: {
  selected: boolean;
  title: string;
  detail: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.choice, selected ? styles.choiceSelected : undefined]}
      onPress={onPress}
    >
      <View
        style={[styles.radio, selected ? styles.radioSelected : undefined]}
      />
      <View style={styles.choiceText}>
        <Text style={styles.vehicle}>{title}</Text>
        <Text style={uiStyles.muted}>{detail}</Text>
      </View>
    </Pressable>
  );
}
const label = (value: JobView) => value[0].toUpperCase() + value.slice(1);
const styles = StyleSheet.create({
  segment: {
    backgroundColor: colors.secondary,
    padding: 3,
    borderRadius: radii.sm,
    gap: 3,
  },
  segmentItem: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: 8,
  },
  segmentActive: { backgroundColor: colors.surface },
  segmentText: { color: colors.text, fontWeight: "800" },
  offline: {
    color: colors.warning,
    backgroundColor: "#FFF1D7",
    padding: spacing.md,
    borderRadius: radii.sm,
  },
  time: { color: colors.text, fontSize: 20, fontWeight: "900" },
  vehicle: { color: colors.text, fontSize: 17, fontWeight: "900" },
  assignment: { color: colors.primary, fontSize: 11, fontWeight: "900" },
  detailTime: { color: colors.text, fontSize: 24, fontWeight: "900" },
  eta: { color: colors.primary, fontWeight: "900" },
  heroVehicle: { color: colors.text, fontSize: 28, fontWeight: "900" },
  actions: { flexDirection: "row", gap: spacing.sm },
  action: { flex: 1 },
  sectionTitle: {
    color: colors.primary,
    fontWeight: "900",
    fontSize: 11,
    letterSpacing: 1,
  },
  backdrop: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(10,30,26,0.38)",
  },
  sheet: {
    maxHeight: "86%",
    backgroundColor: colors.surface,
    borderTopLeftRadius: 26,
    borderTopRightRadius: 26,
    padding: spacing.xl,
    gap: spacing.md,
  },
  choice: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
  },
  choiceSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.secondary,
  },
  choiceText: { flex: 1 },
  radio: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: colors.border,
  },
  radioSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  timelineRow: {
    flexDirection: "row",
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  timelineTime: {
    width: 66,
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "800",
  },
  timelineBody: { flex: 1, gap: 2 },
});
