import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import NetInfo from "@react-native-community/netinfo";
import { useQueryClient } from "@tanstack/react-query";

import { DatePickerField } from "../components/pickers";
import {
  AppButton,
  Card,
  EmptyState,
  MetricCard,
  ScreenTitle,
  Skeleton,
  StatusChip,
  uiStyles,
} from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import {
  canConfirmCashHandover,
  cashDifference,
  cashDifferenceLabel,
  expenseAmountMinor,
  expenseCategories,
} from "../finance/financeState";
import { ClientEventIdStore } from "../idempotency/clientEventId";
import type { CashPendingStaff, StaffContext } from "../lib";
import {
  useCashReconciliationMutation,
  useCashReconciliationsQuery,
  useExpenseMutation,
  useExpensesQuery,
  useFinanceOverviewQuery,
  useJobsQuery,
  usePendingCashDetailQuery,
  usePendingCashQuery,
  useStaffQuery,
  useTeamsQuery,
  useVoidExpenseMutation,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";
import { operationalScope } from "../cache/policy";

type FinanceSection = "overview" | "expenses" | "cash";

const iso = (date: Date) => date.toISOString().slice(0, 10);
const money = (currency: string, amount: number) =>
  `${currency} ${(amount / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
const label = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export function FinanceScreen({
  context,
  onBack,
}: {
  context: StaffContext;
  onBack: () => void;
}) {
  const [period, setPeriod] = useState<"today" | "week" | "month" | "custom">(
    "month",
  );
  const [customStart, setCustomStart] = useState(iso(new Date()));
  const [customEnd, setCustomEnd] = useState(iso(new Date()));
  const range = useMemo(() => {
    if (period === "custom") return { start: customStart, end: customEnd };
    const endDate = new Date();
    const startDate = new Date(endDate);
    if (period === "week") startDate.setDate(endDate.getDate() - 6);
    if (period === "month") startDate.setDate(1);
    return { start: iso(startDate), end: iso(endDate) };
  }, [customEnd, customStart, period]);
  const [section, setSection] = useState<FinanceSection>("overview");
  const queryClient = useQueryClient();
  const overview = useFinanceOverviewQuery(context, range.start, range.end);
  const expenses = useExpensesQuery(context, range.start, range.end);
  const pending = usePendingCashQuery(context);
  const reconciliations = useCashReconciliationsQuery(context);
  const refreshing =
    overview.isRefetching ||
    expenses.isRefetching ||
    pending.isRefetching ||
    reconciliations.isRefetching;
  async function refresh() {
    await Promise.all([
      overview.refetch(),
      expenses.refetch(),
      pending.refetch(),
      reconciliations.refetch(),
      queryClient.invalidateQueries({
        queryKey: ["expenses", operationalScope(context)],
        refetchType: "active",
      }),
    ]);
  }
  return (
    <ScrollView
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />
      }
      contentContainerStyle={uiStyles.content}
    >
      <AppButton title="Back to reports" tone="secondary" onPress={onBack} />
      <ScreenTitle
        eyebrow="MANAGER"
        title="Finance"
        subtitle="Operational cash, expenses and profitability"
      />
      <View style={styles.tabs}>
        {(["today", "week", "month", "custom"] as const).map((item) => (
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected: period === item }}
            key={item}
            onPress={() => setPeriod(item)}
            style={[styles.period, period === item ? styles.periodActive : undefined]}
          >
            <Text style={styles.periodText}>{item.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>
      {period === "custom" ? (
        <View style={styles.customDates}>
          <DatePickerField label="From" value={customStart} maximumDate={new Date()} onChange={setCustomStart} />
          <DatePickerField label="To" value={customEnd} maximumDate={new Date()} onChange={setCustomEnd} />
        </View>
      ) : null}
      <View style={styles.tabs}>
        {(["overview", "expenses", "cash"] as const).map((item) => (
          <Pressable
            accessibilityRole="tab"
            accessibilityState={{ selected: section === item }}
            key={item}
            onPress={() => setSection(item)}
            style={[styles.tab, section === item ? styles.tabActive : undefined]}
          >
            <Text style={styles.tabText}>{label(item)}</Text>
          </Pressable>
        ))}
      </View>
      {section === "overview" ? (
        <Overview value={overview.data} pending={overview.isPending} error={overview.error} />
      ) : section === "expenses" ? (
        <Expenses context={context} start={range.start} end={range.end} />
      ) : (
        <Cash context={context} />
      )}
    </ScrollView>
  );
}

function Overview({
  value,
  pending,
  error,
}: {
  value: ReturnType<typeof useFinanceOverviewQuery>["data"];
  pending: boolean;
  error: Error | null;
}) {
  if (pending) return <Skeleton rows={5} />;
  if (!value)
    return (
      <EmptyState
        title="Finance unavailable"
        body={domainErrorMessage(error, "Pull down to try again.")}
      />
    );
  return (
    <>
      <Text style={styles.section}>THIS MONTH</Text>
      <View style={styles.metrics}>
        <MetricCard label="Booked sales" value={money(value.currency_code, value.booked_sales_minor)} />
        <MetricCard label="Collected" value={money(value.currency_code, value.collected_revenue_minor)} />
        <MetricCard label="Outstanding" value={money(value.currency_code, value.outstanding_minor)} />
        <MetricCard label="Expenses" value={money(value.currency_code, value.expenses_minor)} />
        <MetricCard
          label="Operational profit"
          value={money(value.currency_code, value.operational_profit_minor)}
        />
        <MetricCard label="Margin" value={`${value.margin_percent.toFixed(1)}%`} />
        <MetricCard label="Cash awaiting handover" value={money(value.currency_code, value.cash_pending_minor)} />
        <MetricCard label="Cash short / over" value={money(value.currency_code, value.cash_short_over_minor)} />
      </View>
      <Text style={styles.section}>EXPENSE MIX</Text>
      {value.expense_categories.length ? (
        value.expense_categories.map((item) => (
          <Card key={item.category}>
            <View style={uiStyles.row}>
              <Text style={styles.cardTitle}>{label(item.category)}</Text>
              <Text style={styles.amount}>{money(value.currency_code, item.amount_minor)}</Text>
            </View>
            <Text style={uiStyles.muted}>{item.percentage.toFixed(1)}% of expenses</Text>
          </Card>
        ))
      ) : (
        <EmptyState title="No expenses this month" />
      )}
      <Text style={styles.section}>DIRECT TEAM CONTRIBUTION</Text>
      {value.team_contributions.map((item) => (
        <Card key={item.team_id}>
          <Text style={styles.cardTitle}>{item.team_name}</Text>
          <Text style={uiStyles.body}>
            Contribution {money(value.currency_code, item.direct_contribution_minor)}
          </Text>
          <Text style={uiStyles.muted}>
            Collected {money(value.currency_code, item.collected_revenue_minor)} · Direct expenses{" "}
            {money(value.currency_code, item.direct_expenses_minor)} · {item.completed_jobs} jobs
          </Text>
        </Card>
      ))}
    </>
  );
}

function Expenses({
  context,
  start,
  end,
}: {
  context: StaffContext;
  start: string;
  end: string;
}) {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "voided">("");
  const [staffFilter, setStaffFilter] = useState("");
  const [teamFilter, setTeamFilter] = useState("");
  const [cursors, setCursors] = useState([""]);
  const staff = useStaffQuery(context);
  const teams = useTeamsQuery(context);
  const filters = useMemo(
    () => ({
      search: deferredSearch.trim() || undefined,
      category: categoryFilter || undefined,
      payment_method: methodFilter || undefined,
      status: statusFilter || undefined,
      staff_id: staffFilter || undefined,
      team_id: teamFilter || undefined,
    }),
    [
      categoryFilter,
      deferredSearch,
      methodFilter,
      staffFilter,
      statusFilter,
      teamFilter,
    ],
  );
  useEffect(() => setCursors([""]), [filters, start, end]);
  const query = useExpensesQuery(
    context,
    start,
    end,
    filters,
    cursors[cursors.length - 1],
  );
  const create = useExpenseMutation(context);
  const voidMutation = useVoidExpenseMutation(context);
  const [adding, setAdding] = useState(false);
  if (query.isPending) return <Skeleton rows={5} />;
  if (!query.data)
    return (
      <EmptyState
        title="Expenses unavailable"
        body={domainErrorMessage(query.error, "Pull down to try again.")}
      />
    );
  return (
    <>
      <Card>
        <Text style={styles.section}>TOTAL EXPENSES</Text>
        <Text style={styles.total}>{money(query.data.currency_code, query.data.total_expenses_minor)}</Text>
        <AppButton title="Add expense" onPress={() => setAdding(true)} />
      </Card>
      <Card>
        <Text style={styles.cardTitle}>Filters</Text>
        <TextInput
          accessibilityLabel="Search expenses"
          placeholder="Search description, supplier or reference"
          value={search}
          onChangeText={setSearch}
          style={uiStyles.field}
        />
        <FilterChoices
          values={["", ...expenseCategories]}
          selected={categoryFilter}
          onChange={setCategoryFilter}
          emptyLabel="All categories"
        />
        <FilterChoices
          values={["", "cash", "card", "bank_transfer", "company_card", "other"]}
          selected={methodFilter}
          onChange={setMethodFilter}
          emptyLabel="All methods"
        />
        <FilterChoices
          values={["", "active", "voided"]}
          selected={statusFilter}
          onChange={(value) => setStatusFilter(value as "" | "active" | "voided")}
          emptyLabel="All statuses"
        />
        <FilterChoices
          values={["", ...(staff.data?.map((item) => item.id) ?? [])]}
          labels={Object.fromEntries(staff.data?.map((item) => [item.id, item.display_name]) ?? [])}
          selected={staffFilter}
          onChange={setStaffFilter}
          emptyLabel="All staff"
        />
        <FilterChoices
          values={["", ...(teams.data?.map((item) => item.id) ?? [])]}
          labels={Object.fromEntries(teams.data?.map((item) => [item.id, item.name]) ?? [])}
          selected={teamFilter}
          onChange={setTeamFilter}
          emptyLabel="All teams"
        />
      </Card>
      {adding ? (
        <ExpenseForm
          context={context}
          pending={create.isPending}
          onCancel={() => setAdding(false)}
          onSave={async (body) => {
            const network = await NetInfo.fetch();
            if (!network.isConnected) {
              Alert.alert("You're offline", "Expense changes require an internet connection.");
              return;
            }
            try {
              await create.mutateAsync(body);
              setAdding(false);
              Alert.alert("Expense saved");
            } catch (error) {
              Alert.alert(
                "Expense not saved",
                domainErrorMessage(error, "The server did not confirm this expense."),
              );
              throw error;
            }
          }}
        />
      ) : null}
      {query.data.items.map((item) => (
        <Card key={item.id}>
          <View style={uiStyles.row}>
            <View style={styles.flex}>
              <Text style={styles.cardTitle}>{item.description}</Text>
              <Text style={uiStyles.muted}>
                {item.expense_date} · {label(item.category)} · {label(item.payment_method)}
              </Text>
            </View>
            <Text style={styles.amount}>{money(item.currency_code, item.amount_minor)}</Text>
          </View>
          <StatusChip value={item.status} />
          {item.status === "active" ? (
            <AppButton
              title="Void expense"
              tone="danger"
              onPress={() =>
                Alert.alert("Void this expense?", "The ledger entry remains in history.", [
                  { text: "Cancel", style: "cancel" },
                  {
                    text: "Void",
                    style: "destructive",
                    onPress: () =>
                      void voidMutation.mutateAsync({ id: item.id, reason: "Voided by manager" }),
                  },
                ])
              }
            />
          ) : null}
        </Card>
      ))}
      {cursors.length > 1 || query.data.next_cursor ? (
        <View style={styles.pagination}>
          {cursors.length > 1 ? (
            <AppButton
              title="Previous page"
              tone="secondary"
              onPress={() => setCursors((current) => current.slice(0, -1))}
            />
          ) : null}
          {query.data.next_cursor ? (
            <AppButton
              title="Next page"
              tone="secondary"
              onPress={() =>
                setCursors((current) => [...current, query.data.next_cursor ?? ""])
              }
            />
          ) : null}
        </View>
      ) : null}
      {!query.data.items.length ? <EmptyState title="No expenses this month" /> : null}
    </>
  );
}

function FilterChoices({
  values,
  labels = {},
  selected,
  onChange,
  emptyLabel,
}: {
  values: readonly string[];
  labels?: Record<string, string>;
  selected: string;
  onChange: (value: string) => void;
  emptyLabel: string;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={styles.chips}>
        {values.map((item) => (
          <Pressable
            accessibilityRole="radio"
            accessibilityState={{ checked: selected === item }}
            key={item || "all"}
            onPress={() => onChange(item)}
            style={[styles.choice, selected === item ? styles.choiceActive : undefined]}
          >
            <Text style={styles.choiceText}>
              {item ? labels[item] ?? label(item) : emptyLabel}
            </Text>
          </Pressable>
        ))}
      </View>
    </ScrollView>
  );
}

function ExpenseForm({
  context,
  pending,
  onCancel,
  onSave,
}: {
  context: StaffContext;
  pending: boolean;
  onCancel: () => void;
  onSave: (body: object) => Promise<void>;
}) {
  const [expenseDate, setExpenseDate] = useState(iso(new Date()));
  const [category, setCategory] = useState<(typeof expenseCategories)[number]>("fuel");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [description, setDescription] = useState("");
  const [supplier, setSupplier] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [paidByStaffId, setPaidByStaffId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [relatedJobId, setRelatedJobId] = useState("");
  const staff = useStaffQuery(context);
  const teams = useTeamsQuery(context);
  const jobs = useJobsQuery(context, { view: "all", scope: "all", limit: 50 });
  const eventIds = useRef(new ClientEventIdStore()).current;
  const minor = expenseAmountMinor(amount);
  return (
    <Card>
      <Text style={styles.cardTitle}>Add expense</Text>
      <DatePickerField label="Date" value={expenseDate} maximumDate={new Date()} onChange={setExpenseDate} />
      <Text style={uiStyles.label}>CATEGORY</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={styles.chips}>
          {expenseCategories.map((item) => (
            <Pressable
              accessibilityRole="radio"
              accessibilityState={{ checked: category === item }}
              key={item}
              onPress={() => setCategory(item)}
              style={[styles.choice, category === item ? styles.choiceActive : undefined]}
            >
              <Text style={styles.choiceText}>{label(item)}</Text>
            </Pressable>
          ))}
        </View>
      </ScrollView>
      <Text style={uiStyles.label}>AMOUNT</Text>
      <TextInput accessibilityLabel="Expense amount" keyboardType="decimal-pad" placeholder="0.00" value={amount} onChangeText={setAmount} style={uiStyles.field} />
      <Text style={uiStyles.label}>PAYMENT METHOD</Text>
      <View style={styles.chips}>
        {["cash", "card", "bank_transfer", "company_card", "other"].map((item) => (
          <Pressable key={item} onPress={() => setMethod(item)} style={[styles.choice, method === item ? styles.choiceActive : undefined]}>
            <Text style={styles.choiceText}>{label(item)}</Text>
          </Pressable>
        ))}
      </View>
      <TextInput accessibilityLabel="Expense description" placeholder="Description" value={description} onChangeText={setDescription} style={uiStyles.field} />
      <Text style={uiStyles.label}>PAID BY (OPTIONAL)</Text>
      <FilterChoices
        values={["", ...(staff.data?.map((item) => item.id) ?? [])]}
        labels={Object.fromEntries(
          staff.data?.map((item) => [item.id, item.display_name]) ?? [],
        )}
        selected={paidByStaffId}
        onChange={setPaidByStaffId}
        emptyLabel="Not assigned"
      />
      <Text style={uiStyles.label}>TEAM (OPTIONAL)</Text>
      <FilterChoices
        values={["", ...(teams.data?.map((item) => item.id) ?? [])]}
        labels={Object.fromEntries(
          teams.data?.map((item) => [item.id, item.name]) ?? [],
        )}
        selected={teamId}
        onChange={setTeamId}
        emptyLabel="Not assigned"
      />
      <Text style={uiStyles.label}>RELATED JOB (OPTIONAL)</Text>
      <FilterChoices
        values={["", ...(jobs.data?.jobs.map((item) => item.id) ?? [])]}
        labels={Object.fromEntries(
          jobs.data?.jobs.map((item) => [item.id, item.booking_reference]) ?? [],
        )}
        selected={relatedJobId}
        onChange={setRelatedJobId}
        emptyLabel="Not linked"
      />
      <TextInput accessibilityLabel="Supplier" placeholder="Supplier (optional)" value={supplier} onChangeText={setSupplier} style={uiStyles.field} />
      <TextInput accessibilityLabel="Reference" placeholder="Reference (optional)" value={reference} onChangeText={setReference} style={uiStyles.field} />
      <TextInput accessibilityLabel="Notes" placeholder="Notes (optional)" value={notes} onChangeText={setNotes} multiline style={uiStyles.field} />
      <AppButton
        title="Save expense"
        loading={pending}
        disabled={!description.trim() || minor === null}
        onPress={() => {
          const key = JSON.stringify({
            expenseDate,
            category,
            minor,
            method,
            description,
            supplier,
            reference,
            notes,
            paidByStaffId,
            teamId,
            relatedJobId,
          });
          void (async () => {
            try {
              await onSave({
                expense_date: expenseDate,
                category,
                amount_minor: minor,
                payment_method: method,
                description: description.trim(),
                supplier_name: supplier.trim() || null,
                reference_number: reference.trim() || null,
                notes: notes.trim() || null,
                paid_by_staff_id: paidByStaffId || null,
                team_id: teamId || null,
                related_job_id: relatedJobId || null,
                client_event_id: eventIds.get(key),
              });
              eventIds.succeeded(key);
            } catch (error) {
              eventIds.failed(key, error);
            }
          })();
        }}
      />
      <AppButton title="Cancel" tone="secondary" onPress={onCancel} />
    </Card>
  );
}

function Cash({ context }: { context: StaffContext }) {
  const pending = usePendingCashQuery(context);
  const history = useCashReconciliationsQuery(context);
  const [selected, setSelected] = useState<CashPendingStaff | null>(null);
  if (pending.isPending || history.isPending) return <Skeleton rows={5} />;
  return (
    <>
      <Text style={styles.section}>CASH TO COLLECT</Text>
      {pending.data?.items.map((item) => (
        <Pressable key={item.staff_id} onPress={() => setSelected(item)}>
          <Card>
            <View style={uiStyles.row}>
              <View>
                <Text style={styles.cardTitle}>{item.staff_name}</Text>
                <Text style={uiStyles.muted}>{item.payment_count} payments</Text>
              </View>
              <Text style={styles.amount}>{money(item.currency_code, item.expected_cash_minor)}</Text>
            </View>
          </Card>
        </Pressable>
      ))}
      {!pending.data?.items.length ? <EmptyState title="No cash awaiting handover" /> : null}
      {selected ? <CashHandover context={context} staff={selected} onClose={() => setSelected(null)} /> : null}
      <Text style={styles.section}>HANDOVER HISTORY</Text>
      {history.data?.items.map((item) => (
        <Card key={item.id}>
          <View style={uiStyles.row}>
            <View>
              <Text style={styles.cardTitle}>{item.staff_name}</Text>
              <Text style={uiStyles.muted}>{new Date(item.confirmed_at).toLocaleString()} · {item.payment_count} payments</Text>
            </View>
            <StatusChip value={item.status} />
          </View>
          <Text style={uiStyles.body}>Expected {money(item.currency_code, item.expected_cash_minor)}</Text>
          <Text style={uiStyles.body}>Declared {money(item.currency_code, item.declared_cash_minor)}</Text>
          <Text style={item.difference_minor === 0 ? uiStyles.muted : uiStyles.error}>
            {item.difference_label.toUpperCase()} · {money(item.currency_code, item.difference_minor)}
          </Text>
        </Card>
      ))}
    </>
  );
}

function CashHandover({
  context,
  staff,
  onClose,
}: {
  context: StaffContext;
  staff: CashPendingStaff;
  onClose: () => void;
}) {
  const detail = usePendingCashDetailQuery(context, staff.staff_id);
  const reconcile = useCashReconciliationMutation(context);
  const [declared, setDeclared] = useState((staff.expected_cash_minor / 100).toFixed(2));
  const [note, setNote] = useState("");
  const eventIds = useRef(new ClientEventIdStore()).current;
  const declaredMinor = Math.round(Number(declared) * 100);
  const difference = cashDifference(
    detail.data?.expected_cash_minor ?? staff.expected_cash_minor,
    declaredMinor,
  );
  const paymentIds = useMemo(
    () => detail.data?.payments.map((item) => item.payment_transaction_id) ?? [],
    [detail.data],
  );
  if (detail.isPending) return <Skeleton rows={4} />;
  return (
    <Card>
      <Text style={styles.cardTitle}>{staff.staff_name}</Text>
      <Text style={styles.total}>Expected {money(staff.currency_code, detail.data?.expected_cash_minor ?? 0)}</Text>
      {detail.data?.payments.map((item) => (
        <View key={item.payment_transaction_id} style={uiStyles.row}>
          <Text style={uiStyles.body}>{item.booking_reference}</Text>
          <Text style={uiStyles.body}>{money(item.currency_code, item.amount_minor)}</Text>
        </View>
      ))}
      <Text style={uiStyles.label}>CASH HANDED IN</Text>
      <TextInput accessibilityLabel="Cash handed in" keyboardType="decimal-pad" value={declared} onChangeText={setDeclared} style={uiStyles.field} />
      <Text style={difference === 0 ? uiStyles.body : uiStyles.error}>
        Difference {money(staff.currency_code, difference)} · {cashDifferenceLabel(difference).toUpperCase()}
      </Text>
      {difference !== 0 ? (
        <TextInput accessibilityLabel="Cash discrepancy reason" placeholder="Reason required" value={note} onChangeText={setNote} multiline style={uiStyles.field} />
      ) : null}
      <AppButton
        title={difference === 0 ? "Confirm handover" : "Confirm discrepancy"}
        loading={reconcile.isPending}
        disabled={!canConfirmCashHandover(paymentIds.length, declaredMinor, difference, note)}
        onPress={() =>
          void (async () => {
            const network = await NetInfo.fetch();
            if (!network.isConnected) {
              Alert.alert("You're offline", "Cash handover requires an internet connection.");
              return;
            }
            try {
              const key = JSON.stringify({
                staffId: staff.staff_id,
                paymentIds,
                declaredMinor,
                note: note.trim(),
              });
              await reconcile.mutateAsync({
                staff_id: staff.staff_id,
                payment_transaction_ids: paymentIds,
                declared_cash_minor: declaredMinor,
                note: note.trim() || null,
                client_event_id: eventIds.get(key),
              });
              eventIds.succeeded(key);
              onClose();
              Alert.alert("Cash handover confirmed");
            } catch (error) {
              const key = JSON.stringify({
                staffId: staff.staff_id,
                paymentIds,
                declaredMinor,
                note: note.trim(),
              });
              eventIds.failed(key, error);
              Alert.alert(
                "Handover not confirmed",
                domainErrorMessage(error, "The server did not confirm this handover."),
              );
            }
          })()
        }
      />
      <AppButton title="Cancel" tone="secondary" onPress={onClose} />
    </Card>
  );
}

const styles = StyleSheet.create({
  tabs: { flexDirection: "row", gap: spacing.xs },
  tab: { flex: 1, padding: spacing.md, borderRadius: radii.sm, backgroundColor: colors.secondary, alignItems: "center" },
  tabActive: { backgroundColor: colors.primary },
  tabText: { color: colors.text, fontWeight: "900", fontSize: 12 },
  period: { flex: 1, alignItems: "center", paddingVertical: spacing.sm, borderRadius: radii.sm },
  periodActive: { backgroundColor: colors.surface },
  periodText: { color: colors.text, fontSize: 10, fontWeight: "900" },
  customDates: { gap: spacing.sm },
  section: { color: colors.textSecondary, fontWeight: "900", fontSize: 12, letterSpacing: 1.2, marginTop: spacing.sm },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  cardTitle: { color: colors.text, fontSize: 17, fontWeight: "900" },
  amount: { color: colors.text, fontSize: 15, fontWeight: "900" },
  total: { color: colors.text, fontSize: 26, fontWeight: "900" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  choice: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, borderRadius: radii.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  choiceActive: { borderColor: colors.primary, backgroundColor: colors.secondary },
  choiceText: { color: colors.text, fontWeight: "800", fontSize: 12 },
  flex: { flex: 1 },
  pagination: { gap: spacing.sm },
});
