import { useEffect, useMemo, useRef, useState } from "react";
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
import { DatePickerField, TimePickerField, toIsoDate } from "../components/pickers";
import { ElapsedTimer } from "../components/ElapsedTimer";
import { JobQualityControls } from "../components/JobQualityControls";
import { CashTenderModal } from "../components/CashTenderModal";
import { OperationsCalendar } from "../components/OperationsCalendar";
import { ApiError, domainErrorMessage } from "../errors/domainErrors";
import { expenseAmountMinor } from "../finance/financeState";
import { successHaptic } from "../haptics";
import { tripLocationFailureMessage } from "../location/startTripLocation";
import { expoTripLocationSource } from "../location/expoTripLocation";
import { runStartTripFlow } from "../location/startTripFlow";
import { reportTripApiPreflightFailure } from "../location/tripDiagnostics";
import { ClientEventIdStore } from "../idempotency/clientEventId";
import {
  JobActionPreflightError,
  submitJobAction,
  type JobAction,
} from "../jobs/jobActions";
import type {
  Job,
  JobFilters,
  Profile,
  StaffContext,
} from "../lib";
import { customerEmailUrl } from "../jobs/customerContact";
import {
  useAssignJobMutation,
  useAssignmentOptionsQuery,
  useBusinessSettingsQuery,
  useCashPaymentMutation,
  useExpenseMutation,
  useJobActionMutation,
  useJobCommunicationsQuery,
  useJobQualityQuery,
  useJobQuery,
  useJobsQuery,
  useNotifyCustomerDelayMutation,
  useRescheduleMutation,
  useStaffQuery,
} from "../queries/operations";
import {
  assignmentLabel,
  assignmentSourceLabel,
  shouldShowPagination,
} from "../cache/policy";
import { colors, radii, spacing } from "../theme";
import { normalizeCustomerSearch } from "../search/customerSearch";
import { hourlyQuickTimes } from "../scheduling/exactTime";

export type JobView =
  | "today"
  | "upcoming"
  | "history"
  | "unassigned"
  | "all"
  | "calendar";
export type JobsNavigationState = { view: JobView; offset: number };
const today = () => new Date().toISOString().slice(0, 10);
const formatTime = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

function formatClockTime(value: string): string {
  const [hours, minutes] = value.split(":").map(Number);
  const date = new Date(2000, 0, 1, hours, minutes);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export function JobsScreen({
  context,
  navigationState = { view: "today", offset: 0 },
  onNavigationStateChange,
  initialJobId,
  onInitialJobClosed,
}: {
  context: StaffContext;
  navigationState?: JobsNavigationState;
  onNavigationStateChange?: (value: JobsNavigationState) => void;
  initialJobId?: string | null;
  onInitialJobClosed?: () => void;
}) {
  const canManage = capabilities(context.role).canViewAllJobs;
  const views: JobView[] = canManage
    ? ["today", "upcoming", "unassigned", "history", "all", "calendar"]
    : ["today", "upcoming", "history", "calendar"];
  const [view, setView] = useState<JobView>(navigationState.view);
  const [offset, setOffset] = useState(navigationState.offset);
  const [selected, setSelected] = useState<Job | null>(null);
  const [selectedCalendarJobId, setSelectedCalendarJobId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  function updateNavigation(value: JobsNavigationState) {
    setView(value.view);
    setOffset(value.offset);
    onNavigationStateChange?.(value);
  }
  useEffect(() => {
    if (view !== "all") {
      setSearch("");
      return;
    }
    const timer = setTimeout(() => {
      const normalized = normalizeCustomerSearch(searchText);
      setSearch(normalized);
      setOffset(0);
      onNavigationStateChange?.({ view: "all", offset: 0 });
    }, 300);
    return () => clearTimeout(timer);
  }, [onNavigationStateChange, searchText, view]);
  const filters = useMemo<JobFilters>(
    () => ({
      view: view === "calendar" ? "all" : view,
      scope: canManage ? "all" : "my",
      ...(view === "today" ? { date: today() } : {}),
      ...(view === "all" && search ? { search } : {}),
      offset,
      limit: 50,
    }),
    [canManage, offset, search, view],
  );
  const query = useJobsQuery(context, filters, view !== "calendar");
  const jobs = query.data?.jobs ?? [];
  const searchPending =
    view === "all" &&
    (normalizeCustomerSearch(searchText) !== search ||
      (Boolean(search) && query.isFetching));
  if (initialJobId)
    return (
      <JobDetailById
        context={context}
        jobId={initialJobId}
        onBack={onInitialJobClosed ?? (() => undefined)}
      />
    );
  if (selectedCalendarJobId)
    return (
      <JobDetailById
        context={context}
        jobId={selectedCalendarJobId}
        onBack={() => setSelectedCalendarJobId(null)}
      />
    );
  if (selected)
    return (
      <JobDetail
        context={context}
        initial={selected}
        onBack={() => setSelected(null)}
      />
    );
  const tabs = (
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
          onPress={() => updateNavigation({ view: item, offset: 0 })}
        >
          <Text style={styles.segmentText}>{label(item)}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
  if (view === "calendar")
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <ScreenTitle title="Jobs" subtitle="Monthly operations calendar" />
        {tabs}
        <OperationsCalendar
          context={context}
          onOpenJob={setSelectedCalendarJobId}
        />
      </ScrollView>
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
      {tabs}
      {view === "all" ? (
        <View style={styles.searchRow}>
          <TextInput
            accessibilityLabel="Search customer name"
            autoCapitalize="words"
            autoCorrect={false}
            placeholder="Search customer"
            placeholderTextColor={colors.textSecondary}
            selectionColor={colors.primary}
            returnKeyType="search"
            style={[uiStyles.field, styles.searchField]}
            value={searchText}
            onChangeText={setSearchText}
          />
          {searchText ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Clear customer search"
              onPress={() => setSearchText("")}
            >
              <Text style={uiStyles.link}>Clear</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
      {searchPending ? <Text style={uiStyles.muted}>Searching…</Text> : null}
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
          title={search ? "No matching customers" : `No ${view} jobs`}
          body={
            search
              ? `No jobs matched “${search}”. Try another customer name.`
              : "Pull to refresh or choose another view."
          }
        />
      )}
    </ScrollView>
  );
}

function JobDetailById({
  context,
  jobId,
  onBack,
}: {
  context: StaffContext;
  jobId: string;
  onBack: () => void;
}) {
  const query = useJobQuery(context, jobId);
  if (query.isPending) return <Skeleton rows={6} />;
  if (query.isError || !query.data)
    return (
      <EmptyState
        title="Job unavailable"
        body={domainErrorMessage(query.error, "We couldn't load this job.")}
        action={<AppButton title="Back" onPress={onBack} />}
      />
    );
  return <JobDetail context={context} initial={query.data} onBack={onBack} />;
}

function JobCard({ job }: { job: Job }) {
  useEffect(() => {
    if (
      __DEV__ &&
      (job.assigned_team_id || job.assigned_staff_id) &&
      !job.assigned_team_name &&
      !job.assigned_staff_name
    ) {
      console.warn("[Trifecta Assignment] assigned_name_missing", {
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
  const cashMutation = useCashPaymentMutation(context);
  const expenseMutation = useExpenseMutation(context);
  const canManageJob = capabilities(context.role).canAssignJobs;
  const communications = useJobCommunicationsQuery(
    context,
    job.id,
    canManageJob,
  );
  const delayMutation = useNotifyCustomerDelayMutation(context, job.id);
  const actionEventIds = useRef(new ClientEventIdStore()).current;
  const qualityEnabled = ["arrived", "in_progress", "completed"].includes(
    job.status,
  );
  const qualityQuery = useJobQualityQuery(context, job.id, qualityEnabled);
  const [assignment, setAssignment] = useState(false);
  const [reschedule, setReschedule] = useState(false);
  const [cashTender, setCashTender] = useState(false);
  const [directExpense, setDirectExpense] = useState(false);
  const [delayNotice, setDelayNotice] = useState(false);
  const [tripStage, setTripStage] = useState<
    "idle" | "getting_location" | "starting_trip"
  >("idle");
  function confirmNoEta(
    failure: Parameters<typeof tripLocationFailureMessage>[0],
  ) {
    return new Promise<boolean>((resolve) => {
      Alert.alert(
        "Location unavailable",
        tripLocationFailureMessage(failure),
        [
          { text: "Cancel", style: "cancel", onPress: () => resolve(false) },
          { text: "Start without ETA", onPress: () => resolve(true) },
        ],
        { cancelable: true, onDismiss: () => resolve(false) },
      );
    });
  }
  async function startTrip() {
    try {
      const updated = await runStartTripFlow({
        source: expoTripLocationSource,
        confirmFallback: confirmNoEta,
        onStage: setTripStage,
        submit: (origin) =>
          submitJobAction(
            actionMutation.mutateAsync,
            actionEventIds,
            job.id,
            "start-trip",
            { origin },
            reportTripApiPreflightFailure,
          ),
      });
      if (!updated) return;
      await successHaptic();
      const etaMinutes = updated.estimated_arrival_at
        ? Math.max(
            0,
            Math.ceil(
              (Date.parse(updated.estimated_arrival_at) - Date.now()) / 60_000,
            ),
          )
        : null;
      Alert.alert(
        "Trip started",
        etaMinutes === null
          ? "ETA is unavailable. Customer notification queued."
          : `Estimated arrival in ${etaMinutes} min. Customer notification queued.`,
        [
          {
            text: "Navigate",
            onPress: () => void Linking.openURL(updated.location_url),
          },
          { text: "Close", style: "cancel" },
        ],
      );
    } catch (error) {
      Alert.alert(
        "Unable to start trip",
        error instanceof JobActionPreflightError
          ? "The app could not prepare this action. Please try again."
          : domainErrorMessage(
              error,
              "The server did not confirm this action. Retry safely.",
            ),
      );
    }
  }
  async function action(name: Exclude<JobAction, "start-trip">) {
    try {
      const updated = await submitJobAction(
        actionMutation.mutateAsync,
        actionEventIds,
        job.id,
        name,
      );
      await successHaptic();
      if (name === "complete" && updated.consumption?.has_attention) {
        Alert.alert(
          "Job completed",
          "Inventory needs manager review. The customer workflow is complete.",
        );
      }
    } catch (error) {
      Alert.alert(
        "Action not completed",
        error instanceof JobActionPreflightError
          ? "The app could not prepare this action. Please try again."
          : domainErrorMessage(
              error,
              "The server did not confirm this action. Retry safely.",
            ),
      );
    }
  }
  async function completeCashPayment(
    tenderedMinor: number,
    changeMinor: number,
  ) {
    const eventKey = `${job.id}:cash-payment:${tenderedMinor}`;
    try {
      const receipt = await cashMutation.mutateAsync({
        jobId: job.id,
        body: {
          client_event_id: actionEventIds.get(eventKey),
          client_timestamp: new Date().toISOString(),
          tendered_minor: tenderedMinor,
          change_minor: changeMinor,
        },
      });
      actionEventIds.succeeded(eventKey);
      await successHaptic();
      setCashTender(false);
      Alert.alert(
        "Payment complete",
        `${receipt.job.currency_code} ${(receipt.amount_applied_minor / 100).toFixed(2)} applied. Return ${receipt.job.currency_code} ${(receipt.change_minor / 100).toFixed(2)} change.`,
      );
    } catch (error) {
      actionEventIds.failed(eventKey, error);
      Alert.alert(
        "Payment not completed",
        domainErrorMessage(
          error,
          "The server did not confirm this payment. Retry safely.",
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
        <View style={styles.action}>
          <AppButton
            title="Email"
            tone="secondary"
            onPress={() => void Linking.openURL(customerEmailUrl(job.customer_email))}
          />
        </View>
      </View>
      {qualityEnabled ? (
        <JobQualityControls
          context={context}
          job={job}
          quality={qualityQuery.data}
          pending={qualityQuery.isPending}
          error={qualityQuery.error}
          onRetry={() => void qualityQuery.refetch()}
        />
      ) : null}
      <Card style={styles.primaryActionCard}>
        {job.status === "assigned" ? (
          <>
            <Text style={styles.sectionTitle}>NEXT ACTION</Text>
            <Text style={styles.vehicle}>Ready to leave?</Text>
            <Text style={uiStyles.muted}>
              We’ll use your location for ETA when it is available.
            </Text>
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
              onPress={() => void startTrip()}
            />
          </>
        ) : job.status === "en_route" ? (
          <>
            <Text style={styles.sectionTitle}>ACTIVE TRIP</Text>
            <Text style={styles.vehicle}>Driving to customer</Text>
            {job.en_route_at && <ElapsedTimer startedAt={job.en_route_at} />}
            <Text style={uiStyles.muted}>
              {job.estimated_arrival_at
                ? `ETA ${formatTime(job.estimated_arrival_at)}`
                : "ETA unavailable"}
            </Text>
            <AppButton
              title={
                actionMutation.isPending ? "Confirming…" : "Arrived at location"
              }
              disabled={actionMutation.isPending}
              loading={actionMutation.isPending}
              onPress={() =>
                Alert.alert(
                  "Confirm arrival",
                  "Confirm that you have arrived at the customer location.",
                  [
                    { text: "Cancel", style: "cancel" },
                    {
                      text: "Confirm arrival",
                      onPress: () => void action("arrive"),
                    },
                  ],
                )
              }
            />
          </>
        ) : job.status === "arrived" ? (
          <>
            <Text style={styles.sectionTitle}>AT CUSTOMER</Text>
            <Text style={styles.vehicle}>Arrival confirmed</Text>
            {job.arrived_at && (
              <ElapsedTimer startedAt={job.arrived_at} prefix="Waiting" />
            )}
            <AppButton
              title={actionMutation.isPending ? "Starting…" : "Start wash"}
              disabled={actionMutation.isPending}
              loading={actionMutation.isPending}
              onPress={() => void action("start")}
            />
          </>
        ) : job.status === "in_progress" ? (
          <>
            <Text style={styles.sectionTitle}>WASH IN PROGRESS</Text>
            {job.started_at && <ElapsedTimer startedAt={job.started_at} />}
            <AppButton
              title={actionMutation.isPending ? "Completing…" : "Complete wash"}
              disabled={
                actionMutation.isPending ||
                qualityQuery.data?.can_complete === false
              }
              loading={actionMutation.isPending}
              onPress={() =>
                Alert.alert(
                  "Complete wash?",
                  "Confirm that all booked vehicle services and required checklist items are complete.",
                  [
                    { text: "Keep working", style: "cancel" },
                    {
                      text: "Complete wash",
                      onPress: () => void action("complete"),
                    },
                  ],
                )
              }
            />
          </>
        ) : job.status === "completed" && job.payment_status !== "paid" ? (
          <>
            <Text style={styles.sectionTitle}>PAYMENT REQUIRED</Text>
            <Text style={styles.vehicle}>
              {job.currency_code} {(job.total_amount_minor / 100).toFixed(2)}
            </Text>
            <Text style={uiStyles.muted}>
              Confirm only after the cash is in hand.
            </Text>
            <AppButton
              title="Record cash received"
              disabled={cashMutation.isPending}
              onPress={() => setCashTender(true)}
            />
          </>
        ) : (
          <>
            <Text style={styles.sectionTitle}>JOB STATUS</Text>
            <Text style={styles.vehicle}>
              {job.payment_status === "paid"
                ? "Completed and paid"
                : job.status.replaceAll("_", " ")}
            </Text>
          </>
        )}
      </Card>
      <CashTenderModal
        visible={cashTender}
        dueMinor={job.total_amount_minor}
        currency={job.currency_code}
        pending={cashMutation.isPending}
        onClose={() => setCashTender(false)}
        onComplete={completeCashPayment}
      />
      <DirectExpenseModal
        visible={directExpense}
        job={job}
        pending={expenseMutation.isPending}
        eventIds={actionEventIds}
        onClose={() => setDirectExpense(false)}
        onSave={async (body) => {
          await expenseMutation.mutateAsync(body);
          setDirectExpense(false);
          Alert.alert("Direct expense saved", "The expense is linked to this job.");
        }}
      />
      {canManageJob ? (
        <Card>
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.sectionTitle}>ASSIGNMENT</Text>
              <Text style={uiStyles.muted}>
                {job.assigned_team_name ??
                  job.assigned_staff_name ??
                  "Unassigned"}
              </Text>
              {job.assignment_source ? (
                <Text style={uiStyles.muted}>
                  {assignmentSourceLabel(job)}
                </Text>
              ) : null}
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
          {job.status === "assigned" || job.status === "en_route" ? (
            <AppButton
              title="Notify customer of delay"
              tone="secondary"
              onPress={() => setDelayNotice(true)}
            />
          ) : null}
        </Card>
      ) : null}
      <Card>
        <Text style={styles.sectionTitle}>CUSTOMER</Text>
        <Text style={styles.vehicle}>{job.customer_name}</Text>
        <Text style={uiStyles.body}>{job.customer_phone}</Text>
        <Text style={uiStyles.body}>{job.customer_email}</Text>
      </Card>
      {canManageJob ? (
        <Card>
          <View style={uiStyles.row}>
            <Text style={styles.sectionTitle}>CUSTOMER COMMUNICATIONS</Text>
            {communications.isFetching && communications.data?.length ? (
              <Text style={uiStyles.muted}>Refreshing…</Text>
            ) : null}
          </View>
          {communications.isPending ? (
            <Skeleton rows={3} />
          ) : communications.isError && !communications.data?.length ? (
            <View>
              <Text style={uiStyles.error}>Communication history unavailable.</Text>
              <Pressable onPress={() => void communications.refetch()}>
                <Text style={uiStyles.link}>Try again</Text>
              </Pressable>
            </View>
          ) : communications.data?.length ? (
            communications.data.map((item) => (
              <View key={item.id} style={styles.timelineRow}>
                <Text style={styles.timelineTime}>
                  {formatTime(item.created_at)}
                </Text>
                <View style={styles.timelineBody}>
                  <Text style={styles.vehicle}>{item.event}</Text>
                  <Text style={uiStyles.muted}>
                    {item.state === "sent"
                      ? "Sent"
                      : item.state === "failed"
                        ? "Failed"
                        : "Queued"}
                    {item.detail ? ` · ${item.detail}` : ""}
                  </Text>
                </View>
              </View>
            ))
          ) : (
            <Text style={uiStyles.muted}>No customer messages recorded yet.</Text>
          )}
        </Card>
      ) : null}
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
      {job.consumption ? (
        <Card>
          <View style={uiStyles.row}>
            <Text style={styles.sectionTitle}>CONSUMABLES</Text>
            {job.consumption.has_attention ? (
              <StatusChip value={job.consumption.reviewed_at ? "reviewed" : "needs review"} />
            ) : null}
          </View>
          {job.consumption.status === "no_template" ? (
            <Text style={uiStyles.muted}>No automatic expected usage was configured.</Text>
          ) : (
            job.consumption.lines.map((line) => (
              <View key={line.id} style={styles.consumptionLine}>
                <Text style={styles.vehicle}>{line.item_name}</Text>
                <Text style={uiStyles.muted}>{line.service_name}</Text>
                <Text style={uiStyles.body}>
                  Expected {line.expected_quantity} {line.unit} · Recorded {Number(line.automatic_applied_quantity) + Number(line.preexisting_manual_quantity)} {line.unit}
                </Text>
                {Number(line.additional_manual_quantity) > 0 ? (
                  <Text style={uiStyles.muted}>
                    Additional manual usage {line.additional_manual_quantity} {line.unit}
                  </Text>
                ) : null}
                {Number(line.shortfall_quantity) > 0 ? (
                  <Text style={uiStyles.error}>
                    Needs review: {line.shortfall_quantity} {line.unit} difference
                  </Text>
                ) : null}
              </View>
            ))
          )}
          {job.consumption.source_location_name ? (
            <Text style={uiStyles.muted}>Stock source: {job.consumption.source_location_name}</Text>
          ) : null}
        </Card>
      ) : null}
      {capabilities(context.role).canViewReports ? (
        <Card>
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.sectionTitle}>DIRECT EXPENSES</Text>
              <Text style={styles.vehicle}>
                {job.currency_code} {((job.direct_expenses_total_minor ?? 0) / 100).toFixed(2)}
              </Text>
            </View>
            <Pressable accessibilityRole="button" onPress={() => setDirectExpense(true)}>
              <Text style={uiStyles.link}>Add expense</Text>
            </Pressable>
          </View>
          {job.direct_expenses?.length ? (
            job.direct_expenses.map((expense) => (
              <View key={expense.id} style={styles.consumptionLine}>
                <Text style={uiStyles.body}>{expense.description}</Text>
                <Text style={uiStyles.muted}>
                  {expense.currency_code} {(expense.amount_minor / 100).toFixed(2)} · {expense.expense_date}
                </Text>
              </View>
            ))
          ) : (
            <Text style={uiStyles.muted}>No direct expenses recorded.</Text>
          )}
        </Card>
      ) : null}
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
      {canManageJob ? (
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
          <DelayNotificationSheet
            visible={delayNotice}
            pending={delayMutation.isPending}
            onClose={() => setDelayNotice(false)}
            onNotify={(minutes) => {
              Alert.alert(
                "Notify customer?",
                `Email the customer that the team is approximately ${minutes} minutes late? The appointment time will not change.`,
                [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Queue email",
                    onPress: () => {
                      void delayMutation
                        .mutateAsync(minutes)
                        .then(() => {
                          setDelayNotice(false);
                          Alert.alert("Update queued", "The customer email is queued for sending.");
                        })
                        .catch((error) =>
                          Alert.alert(
                            "Update not queued",
                            domainErrorMessage(error, "Please try again."),
                          ),
                        );
                    },
                  },
                ],
              );
            }}
          />
        </>
      ) : null}
    </ScrollView>
  );
}

function DelayNotificationSheet({
  visible,
  pending,
  onClose,
  onNotify,
}: {
  visible: boolean;
  pending: boolean;
  onClose: () => void;
  onNotify: (minutes: number) => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.vehicle}>Notify customer of a delay</Text>
          <Text style={uiStyles.muted}>
            This sends an email update only. It does not change the appointment time.
          </Text>
          <View style={styles.actions}>
            {[15, 30, 45, 60].map((minutes) => (
              <View key={minutes} style={styles.action}>
                <AppButton
                  title={`${minutes} min`}
                  tone="secondary"
                  disabled={pending}
                  onPress={() => onNotify(minutes)}
                />
              </View>
            ))}
          </View>
          <AppButton title="Cancel" tone="secondary" disabled={pending} onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

function DirectExpenseModal({
  visible,
  job,
  pending,
  eventIds,
  onClose,
  onSave,
}: {
  visible: boolean;
  job: Job;
  pending: boolean;
  eventIds: ClientEventIdStore;
  onClose: () => void;
  onSave: (body: object) => Promise<void>;
}) {
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const minor = expenseAmountMinor(amount);
  const key = `${job.id}:direct-expense:${description.trim()}:${minor}:${method}`;
  async function submit() {
    if (minor === null || !description.trim()) return;
    try {
      await onSave({
        expense_date: today(),
        category: "miscellaneous",
        description: description.trim(),
        amount_minor: minor,
        payment_method: method,
        paid_by_staff_id: null,
        team_id: job.assigned_team_id,
        related_job_id: job.id,
        supplier_name: null,
        reference_number: null,
        notes: null,
        client_event_id: eventIds.get(key),
      });
      eventIds.succeeded(key);
      setDescription("");
      setAmount("");
    } catch (error) {
      eventIds.failed(key, error);
      Alert.alert(
        "Expense not saved",
        domainErrorMessage(error, "The server did not confirm this expense."),
      );
    }
  }
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.vehicle}>Add direct job expense</Text>
          <Text style={uiStyles.muted}>Job {job.booking_reference}</Text>
          <TextInput
            accessibilityLabel="Direct expense description"
            placeholder="Special material or parking"
            placeholderTextColor={colors.textSecondary}
            value={description}
            onChangeText={setDescription}
            style={uiStyles.field}
          />
          <TextInput
            accessibilityLabel="Direct expense amount"
            placeholder="0.00"
            placeholderTextColor={colors.textSecondary}
            keyboardType="decimal-pad"
            value={amount}
            onChangeText={setAmount}
            style={uiStyles.field}
          />
          <View style={styles.paymentMethods}>
            {["cash", "card", "company_card", "bank_transfer", "other"].map((value) => (
              <Pressable
                key={value}
                accessibilityRole="radio"
                accessibilityState={{ checked: method === value }}
                onPress={() => setMethod(value)}
                style={[styles.choice, method === value ? styles.choiceSelected : undefined]}
              >
                <Text style={uiStyles.body}>{value.replaceAll("_", " ")}</Text>
              </Pressable>
            ))}
          </View>
          <AppButton
            title="Save expense"
            loading={pending}
            disabled={pending || minor === null || !description.trim()}
            onPress={() => void submit()}
          />
          <AppButton title="Cancel" tone="secondary" onPress={onClose} />
        </View>
      </View>
    </Modal>
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
  const optionsQuery = useAssignmentOptionsQuery(context, job.id, visible);
  const staffQuery = useStaffQuery(context);
  const mutation = useAssignJobMutation(context);
  const eventIds = useRef(new ClientEventIdStore()).current;
  const [target, setTarget] = useState<{ team_id?: string; staff_id?: string }>(
    {},
  );
  const options = optionsQuery.data ?? [];
  const staff = (staffQuery.data ?? []).filter(
    (item: Profile) => item.is_active,
  );
  async function save(
    mode: "auto" | "manual" = "manual",
    overrideTurnaround = false,
  ) {
    const eventKey = `${job.id}:assignment:${mode}:${target.team_id ?? ""}:${target.staff_id ?? ""}:${job.status}:${overrideTurnaround}`;
    try {
      await mutation.mutateAsync({
        jobId: job.id,
        body: {
          ...(mode === "manual" ? target : {}),
          mode,
          override_turnaround: mode === "manual" && overrideTurnaround,
          confirm_active_reassignment: [
            "en_route",
            "arrived",
            "in_progress",
          ].includes(job.status),
          client_event_id: eventIds.get(eventKey),
          client_timestamp: new Date().toISOString(),
        },
      });
      eventIds.succeeded(eventKey);
      await successHaptic();
      onClose();
    } catch (error) {
      eventIds.failed(eventKey, error);
      Alert.alert(
        "Assignment not completed",
        domainErrorMessage(error, "Review the assignment and try again."),
      );
    }
  }
  function confirmManualAssignment() {
    const selected = options.find((item) => item.team_id === target.team_id);
    if (selected?.status !== "turnaround_conflict") {
      void save("manual");
      return;
    }
    Alert.alert(
      "Short turnaround",
      selected.reason ?? "This team has less than the recommended turnaround between jobs.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Assign anyway",
          style: "destructive",
          onPress: () => void save("manual", true),
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
            <Text style={styles.heroVehicle}>Assign job</Text>
            <Pressable onPress={onClose}>
              <Text style={uiStyles.link}>Close</Text>
            </Pressable>
          </View>
          {optionsQuery.isPending || staffQuery.isPending ? (
            <Skeleton rows={3} />
          ) : null}
          <AppButton
            title={mutation.isPending ? "Assigning…" : "Auto assign"}
            disabled={mutation.isPending}
            loading={mutation.isPending}
            onPress={() => void save("auto")}
          />
          <Text style={styles.sectionTitle}>TEAMS</Text>
          {options.map((item) => (
            <Choice
              key={item.team_id}
              selected={target.team_id === item.team_id}
              title={item.team_name}
              detail={
                item.status === "available"
                  ? `${item.same_day_job_count} jobs · ${item.assigned_minutes} min assigned`
                  : item.reason ?? item.status.replaceAll("_", " ")
              }
              disabled={item.status === "time_conflict" || item.status === "unavailable"}
              onPress={() => {
                setTarget({ team_id: item.team_id });
              }}
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
            onPress={confirmManualAssignment}
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
  const currentAppointment = new Date(job.scheduled_start);
  const [selectedDay, setSelectedDay] = useState(() =>
    toIsoDate(currentAppointment),
  );
  const [selectedTime, setSelectedTime] = useState(() =>
    `${String(currentAppointment.getHours()).padStart(2, "0")}:${String(currentAppointment.getMinutes()).padStart(2, "0")}`,
  );
  const [showCustomTime, setShowCustomTime] = useState(false);
  const settings = useBusinessSettingsQuery(context, visible);
  const mutation = useRescheduleMutation(context, job);
  const dateChoices = upcomingDates(10);
  const weekday = (new Date(`${selectedDay}T12:00:00`).getDay() + 6) % 7;
  const operatingHour = settings.data?.operating_hours.find(
    (item) => item.weekday === weekday,
  );
  const quickTimes = hourlyQuickTimes(
    operatingHour?.opening_time,
    operatingHour?.closing_time,
    Math.max(
      15,
      Math.round(
        (new Date(job.scheduled_end).getTime() -
          new Date(job.scheduled_start).getTime()) /
          60_000,
      ),
    ),
  );
  const selectedDayIsOpen = Boolean(operatingHour?.is_open);
  function changeDay(value: string) {
    setSelectedDay(value);
    setSelectedTime("");
    setShowCustomTime(false);
  }
  async function submit(
    confirmActiveReschedule: boolean,
    overrideTurnaround = false,
  ) {
    if (!selectedTime) return;
    try {
      await mutation.mutateAsync({
        selectedDay,
        startTime: selectedTime,
        confirmActiveReschedule,
        overrideTurnaround,
      });
      await successHaptic();
      onClose();
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.code === "TEAM_TURNAROUND_CONFLICT" &&
        !overrideTurnaround
      ) {
        Alert.alert(
          "Team turnaround conflict",
          "The assigned team needs more travel or preparation time. You can keep the manual assignment and override this buffer.",
          [
            { text: "Choose another time", style: "cancel" },
            {
              text: "Reschedule anyway",
              onPress: () =>
                void submit(confirmActiveReschedule, true),
            },
          ],
        );
        return;
      }
      Alert.alert(
        "Reschedule not completed",
        domainErrorMessage(
          error,
          "That exact time is no longer operationally available. Choose another time and retry.",
        ),
      );
    }
  }
  function confirm() {
    const active =
      job.status === "en_route" ||
      job.status === "arrived" ||
      job.status === "in_progress";
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
          {settings.isPending ? (
            <>
              <Text style={uiStyles.muted}>Loading business hours…</Text>
              <Skeleton rows={3} />
            </>
          ) : settings.isError ? (
            <EmptyState
              title="We couldn't load business hours"
              body="Check your connection and try again."
              action={
                <AppButton
                  title="Try again"
                  onPress={() => void settings.refetch()}
                />
              }
            />
          ) : !selectedDayIsOpen ? (
            <EmptyState
              title="Business closed on this date"
              body="Choose another day to set an exact appointment time."
            />
          ) : (
            <>
              <Text style={styles.sectionTitle}>QUICK HOURLY TIMES</Text>
              <View style={styles.slotGrid}>
                {quickTimes.map((time) => {
                  const selected = selectedTime === time && !showCustomTime;
                  return (
                    <Pressable
                      key={time}
                      accessibilityRole="button"
                      accessibilityState={{ selected }}
                      style={[
                        styles.slotButton,
                        selected ? styles.slotSelected : undefined,
                      ]}
                      onPress={() => {
                        setSelectedTime(time);
                        setShowCustomTime(false);
                      }}
                    >
                      <Text
                        style={[
                          styles.slotTime,
                          selected ? styles.dateSelectedText : undefined,
                        ]}
                      >
                        {formatClockTime(time)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              <AppButton
                title="Choose a custom time"
                tone="secondary"
                onPress={() => setShowCustomTime(true)}
              />
              {showCustomTime ? (
                <TimePickerField
                  label="Exact appointment time"
                  value={selectedTime || operatingHour?.opening_time?.slice(0, 5) || "09:00"}
                  onChange={setSelectedTime}
                />
              ) : null}
              <Text style={uiStyles.muted}>
                The server validates the full service duration, team overlap, and turnaround before saving.
              </Text>
              <AppButton
                title={
                  mutation.isPending ? "Rescheduling…" : "Confirm reschedule"
                }
                disabled={mutation.isPending || !selectedTime}
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
  disabled = false,
}: {
  selected: boolean;
  title: string;
  detail: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityState={{ disabled, selected }}
      style={({ pressed }) => [
        styles.choice,
        selected ? styles.choiceSelected : undefined,
        disabled ? { opacity: 0.48 } : undefined,
        pressed && !disabled ? { opacity: 0.82 } : undefined,
      ]}
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
  searchRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  searchField: {
    flex: 1,
    marginBottom: 0,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  offline: {
    color: colors.warning,
    backgroundColor: colors.warningSurface,
    padding: spacing.md,
    borderRadius: radii.sm,
  },
  time: { color: colors.text, fontSize: 20, fontWeight: "900" },
  vehicle: { color: colors.text, fontSize: 17, fontWeight: "900" },
  assignment: { color: colors.primary, fontSize: 11, fontWeight: "900" },
  detailTime: { color: colors.text, fontSize: 24, fontWeight: "900" },
  eta: { color: colors.primary, fontWeight: "900" },
  primaryActionCard: { borderColor: colors.primary, borderWidth: 2 },
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
  consumptionLine: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
    gap: spacing.xs,
  },
  paymentMethods: { gap: spacing.xs },
  timelineTime: {
    width: 66,
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "800",
  },
  timelineBody: { flex: 1, gap: 2 },
});
