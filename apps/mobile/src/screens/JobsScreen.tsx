import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Linking,
  Modal,
  Pressable,
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
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { DatePickerField, toIsoDate } from "../components/pickers";
import { domainErrorMessage } from "../errors/domainErrors";
import { successHaptic } from "../haptics";
import {
  acquireTripOrigin,
  tripLocationFailureMessage,
  type TripOrigin,
} from "../location/startTripLocation";
import { expoTripLocationSource } from "../location/expoTripLocation";
import type {
  AvailabilitySlot,
  Job,
  JobFilters,
  Profile,
  StaffContext,
  Team,
} from "../lib";
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
import { assignmentLabel, shouldShowPagination } from "../cache/policy";
import { colors, radii, spacing } from "../theme";

export type JobView = "today" | "upcoming" | "history" | "unassigned" | "all";
export type JobsNavigationState = { view: JobView; offset: number };
const today = () => new Date().toISOString().slice(0, 10);
const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

export function JobsScreen({
  context,
  navigationState = { view: "today", offset: 0 },
  onNavigationStateChange,
}: {
  context: StaffContext;
  navigationState?: JobsNavigationState;
  onNavigationStateChange?: (value: JobsNavigationState) => void;
}) {
  const canManage = capabilities(context.role).canViewAllJobs;
  const views: JobView[] = canManage
    ? ["today", "upcoming", "unassigned", "history", "all"]
    : ["today", "upcoming", "history"];
  const [view, setView] = useState<JobView>(navigationState.view);
  const [offset, setOffset] = useState(navigationState.offset);
  const [selected, setSelected] = useState<Job | null>(null);
  function updateNavigation(value: JobsNavigationState) {
    setView(value.view);
    setOffset(value.offset);
    onNavigationStateChange?.(value);
  }
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
              updateNavigation({ view: item, offset: 0 });
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
          {shouldShowPagination(offset, query.data?.next_offset) ? (
            <View style={styles.actions}>
              <View style={styles.action}>
                <AppButton
                  title="Previous"
                  tone="secondary"
                  disabled={offset === 0}
                  onPress={() =>
                    updateNavigation({
                      view,
                      offset: Math.max(0, offset - 50),
                    })
                  }
                />
              </View>
              <View style={styles.action}>
                <AppButton
                  title="Next"
                  tone="secondary"
                  disabled={query.data?.next_offset === null}
                  onPress={() =>
                    updateNavigation({
                      view,
                      offset: query.data?.next_offset ?? offset,
                    })
                  }
                />
              </View>
            </View>
          ) : null}
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
  useEffect(() => {
    if (
      __DEV__ &&
      (job.assigned_team_id || job.assigned_staff_id) &&
      !job.assigned_team_name &&
      !job.assigned_staff_name
    ) {
      console.warn("[AbdWash Assignment] assigned_name_missing", {
        job_id: job.id,
        status: job.status,
        assigned_team_id: job.assigned_team_id,
        assigned_staff_id: job.assigned_staff_id,
      });
    }
  }, [job]);
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
        <Text style={styles.assignment}>{assignmentLabel(job)}</Text>
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
  const [tripStage, setTripStage] = useState<
    "idle" | "getting_location" | "starting_trip"
  >("idle");
  async function submitTrip(origin: TripOrigin | null) {
    setTripStage("starting_trip");
    try {
      const updated = await actionMutation.mutateAsync({
        jobId: job.id,
        action: "start-trip",
        body: {
          client_event_id: crypto.randomUUID(),
          client_timestamp: new Date().toISOString(),
          origin,
        },
      });
      await successHaptic();
      if (!updated.estimated_arrival_at)
        Alert.alert("Trip started", "Trip started, but ETA is unavailable.");
    } catch (error) {
      Alert.alert(
        "Unable to start trip",
        domainErrorMessage(
          error,
          "The server did not confirm this action. Retry safely.",
        ),
      );
    } finally {
      setTripStage("idle");
    }
  }
  async function action(
    name: "start-trip" | "start" | "complete" | "cash-payment",
  ) {
    let body: object = {
      client_event_id: crypto.randomUUID(),
      client_timestamp: new Date().toISOString(),
    };
    try {
      if (name === "start-trip") {
        setTripStage("getting_location");
        const result = await acquireTripOrigin(expoTripLocationSource);
        if (result.origin) {
          await submitTrip(result.origin);
          return;
        }
        setTripStage("idle");
        Alert.alert(
          "Location unavailable",
          tripLocationFailureMessage(result.failure),
          [
            { text: "Cancel", style: "cancel" },
            {
              text: "Start without ETA",
              onPress: () => void submitTrip(null),
            },
          ],
        );
        return;
      }
      await actionMutation.mutateAsync({ jobId: job.id, action: name, body });
      await successHaptic();
    } catch (error) {
      if (name === "start-trip") setTripStage("idle");
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
          title={
            tripStage === "getting_location"
              ? "Getting location…"
              : tripStage === "starting_trip"
                ? "Starting trip…"
                : "Start trip"
          }
          disabled={tripStage !== "idle" || actionMutation.isPending}
          loading={tripStage !== "idle"}
          onPress={() => void action("start-trip")}
        />
      ) : job.status === "en_route" ? (
        <AppButton
          title={actionMutation.isPending ? "Starting…" : "Start wash"}
          disabled={actionMutation.isPending}
          loading={actionMutation.isPending}
          onPress={() => void action("start")}
        />
      ) : job.status === "in_progress" ? (
        <AppButton
          title={actionMutation.isPending ? "Completing…" : "Complete wash"}
          disabled={actionMutation.isPending}
          loading={actionMutation.isPending}
          onPress={() => void action("complete")}
        />
      ) : job.status === "completed" && job.payment_status !== "paid" ? (
        <AppButton
          title={
            actionMutation.isPending ? "Recording…" : "Record cash received"
          }
          disabled={actionMutation.isPending}
          loading={actionMutation.isPending}
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
            loading={mutation.isPending}
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
  const [selectedDay, setSelectedDay] = useState(() => toIsoDate(new Date()));
  const [selection, setSelection] = useState<AvailabilitySlot | null>(null);
  const [resourceId, setResourceId] = useState("");
  const vehicleCount = Math.max(1, job.vehicles.length);
  const availability = useAvailabilityQuery(
    context,
    job.booking_id,
    selectedDay,
    vehicleCount,
    visible,
  );
  const mutation = useRescheduleMutation(context, job);
  const slots = availability.data?.slots ?? [];
  const availableSlots = slots.filter((slot) => slot.available);
  const dateChoices = upcomingDates(10);
  function changeDay(value: string) {
    setSelectedDay(value);
    setSelection(null);
    setResourceId("");
  }
  function chooseSlot(slot: AvailabilitySlot) {
    if (!slot.available || slot.resources.length === 0) return;
    setSelection(slot);
    setResourceId(slot.resources[0].resource_id);
  }
  async function submit(confirmActiveReschedule: boolean) {
    if (!selection || !resourceId) return;
    try {
      await mutation.mutateAsync({
        selectedDay,
        startTime: selection.time,
        resourceId,
        confirmActiveReschedule,
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
  function confirm() {
    const active = job.status === "en_route" || job.status === "in_progress";
    if (!active) {
      void submit(false);
      return;
    }
    Alert.alert(
      "Reset active job?",
      "This job has already started operationally. Rescheduling will reset its trip, ETA, and work timestamps.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Reset and reschedule",
          style: "destructive",
          onPress: () => void submit(true),
        },
      ],
    );
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
          <Text style={styles.sectionTitle}>CHOOSE DATE</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.dateStrip}
          >
            {dateChoices.map((value) => {
              const dateValue = toIsoDate(value);
              const selected = selectedDay === dateValue;
              return (
                <Pressable
                  key={dateValue}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  style={[
                    styles.dateChip,
                    selected ? styles.dateChipSelected : undefined,
                  ]}
                  onPress={() => changeDay(dateValue)}
                >
                  <Text
                    style={[
                      styles.dateWeekday,
                      selected ? styles.dateSelectedText : undefined,
                    ]}
                  >
                    {value.toLocaleDateString(undefined, { weekday: "short" })}
                  </Text>
                  <Text
                    style={[
                      styles.dateNumber,
                      selected ? styles.dateSelectedText : undefined,
                    ]}
                  >
                    {value.getDate()}
                  </Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <DatePickerField
            label="Another date"
            value={selectedDay}
            minimumDate={new Date()}
            onChange={changeDay}
          />
          {availability.isPending ? (
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
          ) : availableSlots.length === 0 ? (
            <EmptyState
              title="No appointments available on this date"
              body="Choose another day."
            />
          ) : (
            <>
              <Text style={styles.sectionTitle}>CHOOSE TIME</Text>
              <View style={styles.slotGrid}>
                {slots.map((slot) => {
                  const selected = selection?.starts_at === slot.starts_at;
                  return (
                    <Pressable
                      key={slot.starts_at}
                      disabled={!slot.available}
                      accessibilityRole="button"
                      accessibilityState={{
                        disabled: !slot.available,
                        selected,
                      }}
                      style={[
                        styles.slotButton,
                        !slot.available ? styles.slotUnavailable : undefined,
                        selected ? styles.slotSelected : undefined,
                      ]}
                      onPress={() => chooseSlot(slot)}
                    >
                      <Text
                        style={[
                          styles.slotTime,
                          selected ? styles.dateSelectedText : undefined,
                        ]}
                      >
                        {formatTime(slot.starts_at)}
                      </Text>
                      {slot.required_slot_count > 1 ? (
                        <Text
                          style={[
                            styles.slotEnd,
                            selected ? styles.dateSelectedText : undefined,
                          ]}
                        >
                          until {formatTime(slot.ends_at)}
                        </Text>
                      ) : null}
                    </Pressable>
                  );
                })}
              </View>
              {selection?.resources.length ? (
                <Card>
                  <Text style={styles.sectionTitle}>AVAILABLE TEAM</Text>
                  {selection.resources.map((resource) => (
                    <Choice
                      key={resource.resource_id}
                      selected={resourceId === resource.resource_id}
                      title={resource.resource_name}
                      detail="Available for this appointment"
                      onPress={() => setResourceId(resource.resource_id)}
                    />
                  ))}
                </Card>
              ) : null}
              {availability.data?.required_slot_count &&
              availability.data.required_slot_count > 1 ? (
                <Text style={uiStyles.muted}>
                  This booking reserves {availability.data.required_slot_count}{" "}
                  consecutive slots for {vehicleCount} vehicles.
                </Text>
              ) : null}
              <AppButton
                title={
                  mutation.isPending ? "Rescheduling…" : "Confirm reschedule"
                }
                disabled={mutation.isPending || !selection || !resourceId}
                loading={mutation.isPending}
                onPress={confirm}
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
function upcomingDates(count: number): Date[] {
  const start = new Date();
  start.setHours(12, 0, 0, 0);
  return Array.from({ length: count }, (_, index) => {
    const value = new Date(start);
    value.setDate(start.getDate() + index);
    return value;
  });
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
  dateStrip: { gap: spacing.sm },
  dateChip: {
    width: 62,
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
  },
  dateChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  dateWeekday: { color: colors.textSecondary, fontSize: 11, fontWeight: "800" },
  dateNumber: { color: colors.text, fontSize: 20, fontWeight: "900" },
  dateSelectedText: { color: colors.white },
  slotGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  slotButton: {
    width: "47%",
    minHeight: 58,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
  },
  slotSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  slotUnavailable: { opacity: 0.35, backgroundColor: colors.surfaceElevated },
  slotTime: { color: colors.text, fontSize: 18, fontWeight: "900" },
  slotEnd: { color: colors.textSecondary, fontSize: 11, fontWeight: "700" },
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
