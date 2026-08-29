import { useEffect, useMemo, useState } from "react";
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
import { AppButton, Card, EmptyState, MetricCard, ScreenTitle, Skeleton, StatusChip, uiStyles } from "../components/ui";
import { domainErrorMessage } from "../errors/domainErrors";
import {
  inventoryCategories,
  getInventoryActionValidation,
  inventoryUnits,
  managementInventoryActions,
  quantityLabel,
  type InventoryAction,
  validQuantity,
} from "../inventory/inventoryState";
import type { InventoryItem, InventoryLocation, StaffContext } from "../lib";
import {
  useInventoryAttentionQuery,
  useBusinessSettingsQuery,
  useCatalogueMutation,
  useInventoryItemsQuery,
  useInventoryLocationsQuery,
  useInventoryMovementsQuery,
  useInventoryMutation,
  useInventoryOverviewQuery,
  useInventoryReviewMutation,
  useInventoryStockQuery,
  useTeamsQuery,
} from "../queries/operations";
import { colors, radii, spacing } from "../theme";

type InventoryTab = "overview" | "catalogue" | "stock" | "movements";
type DraftQuantityLine = { item_id: string; quantity: string };

export function InventoryScreen({
  context,
  onBack,
  onOpenJob,
}: {
  context: StaffContext;
  onBack: () => void;
  onOpenJob: (jobId: string) => void;
}) {
  const management = context.role === "manager" || context.role === "admin";
  const [tab, setTab] = useState<InventoryTab>(management ? "overview" : "stock");
  const [action, setAction] = useState<InventoryAction | null>(null);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [search, setSearch] = useState("");
  const [locationId, setLocationId] = useState("");
  const [status, setStatus] = useState("");
  const overview = useInventoryOverviewQuery(context, management);
  const attention = useInventoryAttentionQuery(context, management);
  const settings = useBusinessSettingsQuery(context, management && tab === "overview");
  const settingsMutation = useCatalogueMutation(context);
  const review = useInventoryReviewMutation(context);
  const items = useInventoryItemsQuery(context, search);
  const locations = useInventoryLocationsQuery(context);
  const stock = useInventoryStockQuery(
    context,
    locationId,
    search,
    status,
    tab === "stock",
  );
  const movements = useInventoryMovementsQuery(
    context,
    locationId,
    tab === "movements",
  );
  const refresh = async () => {
    const requests: Promise<unknown>[] = [
      items.refetch(),
      locations.refetch(),
    ];
    if (tab === "stock") requests.push(stock.refetch());
    if (tab === "movements") requests.push(movements.refetch());
    if (tab === "overview" && management) {
      requests.push(overview.refetch(), attention.refetch(), settings.refetch());
    }
    await Promise.all(requests);
  };
  if (action) {
    return (
      <InventoryActionScreen
        context={context}
        action={action}
        items={items.data?.items ?? []}
        locations={locations.data ?? []}
        initialItem={editingItem}
        onBack={() => {
          setAction(null);
          setEditingItem(null);
        }}
      />
    );
  }
  const pending =
    locations.isPending ||
    (tab === "overview" ? overview.isPending || attention.isPending || settings.isPending : tab === "catalogue" ? items.isPending : tab === "stock" ? stock.isPending : movements.isPending);
  const error = locations.error ?? (tab === "overview" ? overview.error ?? attention.error ?? settings.error : tab === "catalogue" ? items.error : tab === "stock" ? stock.error : movements.error);
  const refreshing = items.isRefetching || locations.isRefetching || stock.isRefetching || movements.isRefetching || overview.isRefetching || attention.isRefetching || settings.isRefetching;
  return (
    <ScrollView
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />}
      contentContainerStyle={uiStyles.content}
    >
      <Pressable onPress={onBack} accessibilityRole="button">
        <Text style={uiStyles.link}>← Management</Text>
      </Pressable>
      <ScreenTitle title="Inventory" subtitle="Authoritative consumables stock" />
      <View style={styles.tabs}>
        {(management ? ["overview", "catalogue", "stock", "movements"] : ["stock", "movements"]).map((value) => (
          <Pressable
            key={value}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === value }}
            onPress={() => setTab(value as InventoryTab)}
            style={[styles.tab, tab === value ? styles.tabActive : undefined]}
          >
            <Text style={styles.tabText}>{value.toUpperCase()}</Text>
          </Pressable>
        ))}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.actions}>
        {managementInventoryActions(context.role).map((value) => (
          <Pressable key={value} onPress={() => setAction(value)} style={styles.action}>
            <Text style={styles.actionText}>{actionLabel(value)}</Text>
          </Pressable>
        ))}
      </ScrollView>
      {tab !== "overview" ? (
        <>
          <TextInput
            accessibilityLabel="Search inventory"
            placeholder="Search item, code, or category"
            placeholderTextColor={colors.textSecondary}
            value={search}
            onChangeText={setSearch}
            style={uiStyles.field}
          />
          <ChoiceRow
            values={[{ id: "", label: "All locations" }, ...(locations.data ?? []).map((item) => ({ id: item.id, label: item.name }))]}
            selected={locationId}
            onSelect={setLocationId}
          />
          {tab === "stock" ? (
            <ChoiceRow
              values={[{ id: "", label: "All" }, { id: "low", label: "Low" }, { id: "out", label: "Out" }]}
              selected={status}
              onSelect={setStatus}
            />
          ) : null}
        </>
      ) : null}
      {error ? <Text style={uiStyles.error}>{domainErrorMessage(error, "Inventory could not load.")}</Text> : null}
      {pending ? <Skeleton rows={4} /> : tab === "overview" ? (
        <InventoryOverviewContent
          value={overview.data ?? null}
          attention={attention.data?.items ?? []}
          locations={(locations.data ?? []).filter((item) => item.is_active)}
          defaultLocationId={effectiveDefaultLocationId(
            locations.data ?? [],
            settings.data?.default_inventory_location_id ?? null,
          )}
          settingDefault={settingsMutation.isPending}
          reviewing={review.isPending}
          onOpenJob={onOpenJob}
          onStockCount={() => setAction("stock_count")}
          onReviewStock={() => setTab("stock")}
          onOpenConsumable={() => setTab("catalogue")}
          onCreateLocation={() => setAction("create_location")}
          onSetDefaultLocation={(default_inventory_location_id) =>
            void settingsMutation
              .mutateAsync({
                action: "update_settings",
                body: { default_inventory_location_id },
              })
              .then(() =>
                Alert.alert(
                  "Stock location saved",
                  "Expected service usage will deduct from this location.",
                ),
              )
              .catch((settingsError) =>
                Alert.alert(
                  "Stock location not saved",
                  domainErrorMessage(
                    settingsError,
                    "The server did not confirm this stock location.",
                  ),
                ),
              )
          }
          onReview={(runId, jobId) =>
            void review
              .mutateAsync({ runId, jobId })
              .then(() => Alert.alert("Inventory reviewed", "The historical quantities were left unchanged."))
              .catch((reviewError) =>
                Alert.alert(
                  "Review not saved",
                  domainErrorMessage(reviewError, "The server did not confirm this review."),
                ),
              )
          }
        />
      ) : tab === "catalogue" ? (
        <CatalogueContent
          items={items.data?.items ?? []}
          onEdit={(item) => {
            setEditingItem(item);
            setAction("edit_item");
          }}
        />
      ) : tab === "stock" ? (
        <StockContent items={stock.data?.items ?? []} />
      ) : (
        <MovementContent items={movements.data?.items ?? []} />
      )}
    </ScrollView>
  );
}

function InventoryOverviewContent({ value, attention, locations, defaultLocationId, settingDefault, reviewing, onOpenJob, onStockCount, onReviewStock, onOpenConsumable, onCreateLocation, onSetDefaultLocation, onReview }: {
  value: ReturnType<typeof useInventoryOverviewQuery>["data"] | null;
  attention: NonNullable<ReturnType<typeof useInventoryAttentionQuery>["data"]>["items"];
  locations: InventoryLocation[];
  defaultLocationId: string;
  settingDefault: boolean;
  reviewing: boolean;
  onOpenJob: (jobId: string) => void;
  onStockCount: () => void;
  onReviewStock: () => void;
  onOpenConsumable: () => void;
  onCreateLocation: () => void;
  onSetDefaultLocation: (locationId: string) => void;
  onReview: (runId: string, jobId: string) => void;
}) {
  const [setupRunId, setSetupRunId] = useState<string | null>(null);
  if (!value) return <EmptyState title="No inventory overview" body="Pull down to try again." />;
  return (
    <>
      {locations.length > 1 ? (
        <Card>
          <Text style={styles.title}>Automatic consumables stock</Text>
          <Text style={uiStyles.muted}>
            Completed services deduct expected usage from this business stock location.
          </Text>
          <ChoiceRow
            values={locations.map((location) => ({
              id: location.id,
              label: location.name,
            }))}
            selected={defaultLocationId}
            onSelect={onSetDefaultLocation}
          />
          {settingDefault ? <Text style={uiStyles.muted}>Saving…</Text> : null}
        </Card>
      ) : null}
      <View style={styles.metrics}>
        <MetricCard label="Active items" value={String(value.active_item_count)} />
        <MetricCard label="Low stock" value={String(value.low_stock_count)} />
        <MetricCard label="Out of stock" value={String(value.out_of_stock_count)} />
        <MetricCard label="Needs review" value={String(value.needs_review_count)} />
      </View>
      {attention.length ? (
        <>
          <Text style={styles.sectionHeading}>NEEDS REVIEW</Text>
          {attention.map((item) => (
            <Card key={item.id}>
              <Text style={styles.title}>Job {item.booking_reference}</Text>
              <Text style={uiStyles.muted}>{item.customer_name}</Text>
              <Text style={uiStyles.body}>{inventoryIssueCopy(item.issue_code)}</Text>
              <AppButton
                title="Open job"
                tone="secondary"
                onPress={() => onOpenJob(item.job_id)}
              />
              {item.issue_code === "SOURCE_LOCATION_MISSING" ||
              item.issue_code === "SOURCE_LOCATION_AMBIGUOUS" ? (
                <>
                  <AppButton
                    title={locations.length ? "Set stock location" : "Create stock location"}
                    tone="secondary"
                    onPress={() =>
                      locations.length
                        ? setSetupRunId(item.id)
                        : onCreateLocation()
                    }
                  />
                  {setupRunId === item.id && locations.length ? (
                    <ChoiceRow
                      values={locations.map((location) => ({
                        id: location.id,
                        label: location.name,
                      }))}
                      selected={defaultLocationId}
                      onSelect={onSetDefaultLocation}
                    />
                  ) : null}
                  <Text style={uiStyles.muted}>
                    Future jobs use the saved location. This historical shortfall is not replayed automatically.
                  </Text>
                </>
              ) : item.issue_code === "INVENTORY_ITEM_INACTIVE" ? (
                <AppButton title="Open consumable setup" tone="secondary" onPress={onOpenConsumable} />
              ) : (
                <>
                  <AppButton title="Review stock" tone="secondary" onPress={onReviewStock} />
                  <AppButton title="Stock count" tone="secondary" onPress={onStockCount} />
                </>
              )}
              <AppButton
                title="Mark reviewed"
                tone="secondary"
                loading={reviewing}
                disabled={reviewing}
                onPress={() => onReview(item.id, item.job_id)}
              />
            </Card>
          ))}
        </>
      ) : null}
      {value.locations.map((location) => (
        <Card key={location.location_id}>
          <Text style={styles.title}>{location.location_name}</Text>
          <Text style={uiStyles.muted}>{location.location_type.replaceAll("_", " ")}</Text>
          <Text style={uiStyles.body}>{location.low_stock_count} low · {location.out_of_stock_count} out</Text>
        </Card>
      ))}
    </>
  );
}

export function effectiveDefaultLocationId(
  locations: InventoryLocation[],
  configuredId: string | null,
): string {
  const active = locations.filter((location) => location.is_active);
  if (configuredId && active.some((location) => location.id === configuredId)) {
    return configuredId;
  }
  if (active.length === 1) return active[0].id;
  const mains = active.filter((location) => location.location_type === "main");
  return mains.length === 1 ? mains[0].id : "";
}

export function inventoryIssueCopy(issueCode: string | null): string {
  if (
    issueCode === "SOURCE_LOCATION_MISSING" ||
    issueCode === "SOURCE_LOCATION_AMBIGUOUS"
  ) {
    return "Automatic stock location is not set.";
  }
  if (issueCode === "INVENTORY_ITEM_INACTIVE") {
    return "A configured consumable is inactive.";
  }
  if (issueCode === "INSUFFICIENT_RECORDED_STOCK") {
    return "Recorded stock is lower than the expected service usage.";
  }
  return "Expected service usage needs a manager review.";
}

function StockContent({ items }: { items: Awaited<ReturnType<typeof import("../lib").getInventoryStock>>["items"] }) {
  if (!items.length) return <EmptyState title="No stock found" body="Receive opening stock or change the filters." />;
  return <>{items.map((item) => (
    <Card key={`${item.item_id}:${item.location_id}`}>
      <View style={uiStyles.row}>
        <View style={styles.flex}>
          <Text style={styles.title}>{item.item_name}</Text>
          <Text style={uiStyles.muted}>{item.location_name} · {item.category.replaceAll("_", " ")}</Text>
        </View>
        <StatusChip value={item.status} />
      </View>
      <Text style={styles.quantity}>{quantityLabel(item.quantity, item.unit)}</Text>
      <Text style={uiStyles.muted}>Low at {quantityLabel(item.threshold, item.unit)}</Text>
    </Card>
  ))}</>;
}

function CatalogueContent({ items, onEdit }: { items: InventoryItem[]; onEdit: (item: InventoryItem) => void }) {
  if (!items.length) return <EmptyState title="No inventory items" body="Create the first catalogue item." />;
  return <>{items.map((item) => (
    <Pressable key={item.id} onPress={() => onEdit(item)} accessibilityRole="button">
      <Card>
        <View style={uiStyles.row}>
          <View style={styles.flex}>
            <Text style={styles.title}>{item.name}</Text>
            <Text style={uiStyles.muted}>{item.category.replaceAll("_", " ")} · {item.unit}</Text>
          </View>
          <StatusChip value={item.is_active ? "active" : "inactive"} />
        </View>
        <Text style={styles.quantity}>{quantityLabel(item.total_quantity, item.unit)}</Text>
        <Text style={uiStyles.link}>Edit item →</Text>
      </Card>
    </Pressable>
  ))}</>;
}

function MovementContent({ items }: { items: Awaited<ReturnType<typeof import("../lib").getInventoryMovements>>["items"] }) {
  if (!items.length) return <EmptyState title="No movements found" body="Stock history will appear here." />;
  return <>{items.map((item) => (
    <Card key={item.id}>
      <View style={uiStyles.row}>
        <Text style={styles.title}>{item.item_name}</Text>
        <Text style={item.signed_quantity < 0 ? styles.negative : styles.positive}>
          {item.signed_quantity > 0 ? "+" : ""}{quantityLabel(item.signed_quantity, item.unit)}
        </Text>
      </View>
      <Text style={uiStyles.muted}>{item.movement_type.replaceAll("_", " ")} · {item.location_name}</Text>
      {item.booking_reference ? <Text style={uiStyles.body}>Job {item.booking_reference}</Text> : null}
      <Text style={uiStyles.muted}>{item.actor_name} · {new Date(item.created_at).toLocaleString()}</Text>
    </Card>
  ))}</>;
}

function InventoryActionScreen({ context, action, items, locations, initialItem, onBack }: {
  context: StaffContext;
  action: InventoryAction;
  items: InventoryItem[];
  locations: InventoryLocation[];
  initialItem: InventoryItem | null;
  onBack: () => void;
}) {
  const mutation = useInventoryMutation(context);
  const teams = useTeamsQuery(context);
  const [name, setName] = useState(initialItem?.name ?? "");
  const [code, setCode] = useState(initialItem?.code ?? "");
  const [category, setCategory] = useState<string>(initialItem?.category ?? inventoryCategories[0]);
  const [unit, setUnit] = useState<string>(initialItem?.unit ?? inventoryUnits[0]);
  const [threshold, setThreshold] = useState(String(initialItem?.default_low_stock_threshold ?? 0));
  const [locationType, setLocationType] = useState("main");
  const [teamId, setTeamId] = useState("");
  const [itemId, setItemId] = useState(items[0]?.id ?? "");
  const [locationId, setLocationId] = useState(locations[0]?.id ?? "");
  const [destinationId, setDestinationId] = useState(locations.find((item) => item.id !== locationId)?.id ?? "");
  const [quantity, setQuantity] = useState("");
  const [draftLines, setDraftLines] = useState<DraftQuantityLine[]>([]);
  const [reason, setReason] = useState("");
  const [jobId, setJobId] = useState("");
  const [expenseAmount, setExpenseAmount] = useState("");
  const selected = useMemo(() => items.find((item) => item.id === itemId), [itemId, items]);
  const isCount = action === "stock_count";
  const requiresLocation = !["create_item", "edit_item", "create_location"].includes(action);
  const hasCurrentLine = Boolean(itemId && validQuantity(quantity, isCount));
  const validation = getInventoryActionValidation(action, {
    name,
    threshold,
    itemId,
    locationId,
    destinationId,
    hasQuantityLine: draftLines.length > 0 || hasCurrentLine,
    reason,
    jobId,
    expenseAmount,
    isEmployee: context.role === "employee",
  });
  useEffect(() => {
    if (!locationId && locations.length) setLocationId(locations[0].id);
  }, [locationId, locations]);
  useEffect(() => {
    if (
      action === "transfer" &&
      (!destinationId || destinationId === locationId)
    ) {
      setDestinationId(locations.find((location) => location.id !== locationId)?.id ?? "");
    }
  }, [action, destinationId, locationId, locations]);
  function addDraftLine() {
    if (!hasCurrentLine) return;
    setDraftLines((current) => {
      const withoutItem = current.filter((line) => line.item_id !== itemId);
      return [...withoutItem, { item_id: itemId, quantity }];
    });
    setQuantity("");
  }
  async function submit() {
    try {
      const submittedLines = draftLines.length
        ? draftLines
        : [{ item_id: itemId, quantity }];
      const quantityLines = submittedLines.map((line) => ({
        item_id: line.item_id,
        quantity: Number(line.quantity),
      }));
      const body = ["create_item", "edit_item"].includes(action)
        ? { name: name.trim(), code: code.trim() || null, category, unit, default_low_stock_threshold: Number(threshold), notes: null }
        : action === "create_location"
          ? { name: name.trim(), location_type: locationType, linked_team_id: teamId || null }
          : action === "transfer"
            ? { from_location_id: locationId, to_location_id: destinationId, lines: quantityLines, notes: reason.trim() || null }
            : action === "receive"
              ? { location_id: locationId, lines: quantityLines.map((line) => ({ ...line, unit_cost_minor: null })), reference_number: reason.trim() || null, supplier_name: null, notes: null, opening_balance: false, record_as_expense: Boolean(expenseAmount), expense_amount_minor: expenseAmount ? Math.round(Number(expenseAmount) * 100) : null, expense_payment_method: expenseAmount ? "company_card" : null }
              : action === "usage"
                ? { location_id: locationId, lines: quantityLines, job_id: jobId.trim() || null, notes: reason.trim() || null }
                : action === "wastage"
                  ? { location_id: locationId, lines: quantityLines, reason: reason.trim() }
                  : { location_id: locationId, lines: submittedLines.map((line) => ({ item_id: line.item_id, counted_quantity: Number(line.quantity) })), reason: reason.trim() };
      await mutation.mutateAsync(
        action === "edit_item" && initialItem
          ? { action, itemId: initialItem.id, body }
          : { action: action as Exclude<InventoryAction, "edit_item">, body },
      );
      Alert.alert("Inventory updated", `${actionLabel(action)} was recorded successfully.`);
      onBack();
    } catch (error) {
      Alert.alert("Inventory not updated", domainErrorMessage(error, "The server did not confirm this stock operation."));
    }
  }
  async function createMainShop() {
    try {
      await mutation.mutateAsync({
        action: "create_location",
        body: { name: "Main Shop", location_type: "main", linked_team_id: null },
      });
      Alert.alert("Main Shop created", "The primary stock location is ready.");
    } catch (error) {
      Alert.alert(
        "Location not created",
        domainErrorMessage(error, "The server did not confirm this location."),
      );
    }
  }
  if (requiresLocation && locations.length === 0) {
    const management = context.role === "manager" || context.role === "admin";
    return (
      <ScrollView contentContainerStyle={uiStyles.content}>
        <Pressable onPress={onBack} accessibilityRole="button">
          <Text style={uiStyles.link}>← Inventory</Text>
        </Pressable>
        <ScreenTitle title={actionLabel(action)} subtitle="A stock location is required" />
        <Card>
          <Text style={styles.title}>No stock location is configured.</Text>
          <Text style={uiStyles.muted}>
            {management
              ? "Create the primary Main Shop location to continue."
              : "Ask a manager to configure an inventory location."}
          </Text>
        </Card>
        {management ? (
          <AppButton
            title="Create Main Shop Location"
            onPress={() => void createMainShop()}
            loading={mutation.isPending}
          />
        ) : null}
      </ScrollView>
    );
  }
  return (
    <ScrollView contentContainerStyle={uiStyles.content}>
      <Pressable onPress={onBack}><Text style={uiStyles.link}>← Inventory</Text></Pressable>
      <ScreenTitle title={actionLabel(action)} subtitle="Stock changes are recorded in the audit ledger" />
      {["create_item", "edit_item"].includes(action) ? (
        <>
          <Field label="Item name" value={name} onChange={setName} placeholder="Interior Cleaner" />
          <Field label="SKU / code (optional)" value={code} onChange={setCode} placeholder="CHEM-001" />
          <Label text="Category" /><ChoiceRow values={inventoryCategories.map((value) => ({ id: value, label: value.replaceAll("_", " ") }))} selected={category} onSelect={setCategory} />
          <Label text="Unit" /><ChoiceRow values={inventoryUnits.map((value) => ({ id: value, label: value }))} selected={unit} onSelect={setUnit} />
          <Field label="Low-stock threshold" value={threshold} onChange={setThreshold} keyboard="decimal-pad" />
        </>
      ) : action === "create_location" ? (
        <>
          <Field label="Location name" value={name} onChange={setName} placeholder="Main Shop" />
          <Label text="Type" /><ChoiceRow values={["main", "mobile_team", "van", "other"].map((value) => ({ id: value, label: value.replaceAll("_", " ") }))} selected={locationType} onSelect={setLocationType} />
          {locationType === "mobile_team" ? <><Label text="Linked team" /><ChoiceRow values={(teams.data ?? []).map((value) => ({ id: value.id, label: value.name }))} selected={teamId} onSelect={setTeamId} /></> : null}
        </>
      ) : (
        <>
          <Label text="Item" /><ChoiceRow values={items.map((value) => ({ id: value.id, label: value.name }))} selected={itemId} onSelect={setItemId} />
          <Label text={action === "transfer" ? "From" : "Location"} />
          {locations.length === 1 ? (
            <View style={styles.selectedLocation}>
              <Text style={styles.selectedLocationText}>{locations[0].name} ✓</Text>
            </View>
          ) : (
            <ChoiceRow values={locations.map((value) => ({ id: value.id, label: value.name }))} selected={locationId} onSelect={setLocationId} />
          )}
          {action === "transfer" ? <><Label text="To" /><ChoiceRow values={locations.filter((value) => value.id !== locationId).map((value) => ({ id: value.id, label: value.name }))} selected={destinationId} onSelect={setDestinationId} /></> : null}
          <Field label={isCount ? "Counted quantity" : `Quantity${selected ? ` (${selected.unit})` : ""}`} value={quantity} onChange={setQuantity} keyboard="decimal-pad" />
          {draftLines.map((line) => {
            const draftItem = items.find((item) => item.id === line.item_id);
            return (
              <Card key={line.item_id}>
                <View style={uiStyles.row}>
                  <View style={styles.flex}>
                    <Text style={styles.title}>{draftItem?.name ?? "Inventory item"}</Text>
                    <Text style={uiStyles.muted}>{quantityLabel(Number(line.quantity), draftItem?.unit ?? "")}</Text>
                  </View>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={`Remove ${draftItem?.name ?? "inventory item"}`}
                    onPress={() => setDraftLines((current) => current.filter((value) => value.item_id !== line.item_id))}
                  >
                    <Text style={uiStyles.link}>Remove</Text>
                  </Pressable>
                </View>
              </Card>
            );
          })}
          <AppButton title="Add another item" tone="secondary" onPress={addDraftLine} disabled={!hasCurrentLine} />
          {action === "usage" ? <Field label="Job ID (required for employees)" value={jobId} onChange={setJobId} placeholder="Job UUID" /> : null}
          {action === "receive" ? <Field label="Purchase total AED (optional expense)" value={expenseAmount} onChange={setExpenseAmount} keyboard="decimal-pad" /> : null}
          <Field label={["wastage", "stock_count"].includes(action) ? "Reason" : "Reference / notes (optional)"} value={reason} onChange={setReason} placeholder={action === "wastage" ? "Spilled during refill" : ""} />
        </>
      )}
      {!validation.canSubmit && validation.reason ? (
        <Text accessibilityRole="alert" style={styles.validationReason}>
          {validation.reason}
        </Text>
      ) : null}
      <AppButton title={actionLabel(action)} onPress={() => void submit()} disabled={!validation.canSubmit} loading={mutation.isPending} />
      {action === "edit_item" && initialItem ? (
        <AppButton
          title={initialItem.is_active ? "Deactivate item" : "Reactivate item"}
          tone={initialItem.is_active ? "danger" : "secondary"}
          loading={mutation.isPending}
          onPress={() => void mutation.mutateAsync({
            action: "edit_item",
            itemId: initialItem.id,
            body: { is_active: !initialItem.is_active },
          }).then(onBack).catch((error) => Alert.alert("Item not updated", domainErrorMessage(error, "The server did not confirm this change.")))}
        />
      ) : null}
    </ScrollView>
  );
}

function Field({ label, value, onChange, placeholder, keyboard }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; keyboard?: "default" | "decimal-pad" }) {
  return <View><Label text={label} /><TextInput accessibilityLabel={label} value={value} onChangeText={onChange} placeholder={placeholder} placeholderTextColor={colors.textSecondary} keyboardType={keyboard} style={uiStyles.field} /></View>;
}

function Label({ text }: { text: string }) { return <Text style={uiStyles.label}>{text.toUpperCase()}</Text>; }

function ChoiceRow({ values, selected, onSelect }: { values: { id: string; label: string }[]; selected: string; onSelect: (value: string) => void }) {
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.choices}>
    {values.map((value) => <Pressable key={value.id || "all"} accessibilityRole="button" accessibilityState={{ selected: selected === value.id }} onPress={() => onSelect(value.id)} style={[styles.choice, selected === value.id ? styles.choiceActive : undefined]}><Text style={[styles.choiceText, selected === value.id ? styles.choiceTextActive : undefined]}>{value.label}</Text></Pressable>)}
  </ScrollView>;
}

function actionLabel(action: InventoryAction) {
  return ({ create_item: "Create item", edit_item: "Edit item", create_location: "Create location", receive: "Receive stock", transfer: "Transfer", usage: "Record usage", wastage: "Record wastage", stock_count: "Stock count" })[action];
}

const styles = StyleSheet.create({
  tabs: { flexDirection: "row", gap: spacing.sm },
  tab: { flex: 1, padding: spacing.md, alignItems: "center", borderBottomWidth: 2, borderBottomColor: colors.border },
  tabActive: { borderBottomColor: colors.primary },
  tabText: { color: colors.text, fontWeight: "900", fontSize: 11 },
  actions: { gap: spacing.sm },
  action: { backgroundColor: colors.secondary, borderRadius: radii.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
  actionText: { color: colors.primary, fontWeight: "900" },
  choices: { gap: spacing.sm, paddingBottom: spacing.xs },
  choice: { borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, backgroundColor: colors.surface },
  choiceActive: { borderColor: colors.primary, backgroundColor: colors.secondary },
  choiceText: { color: colors.textSecondary, textTransform: "capitalize" },
  choiceTextActive: { color: colors.primary, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  title: { color: colors.text, fontSize: 16, fontWeight: "900" },
  quantity: { color: colors.text, fontSize: 22, fontWeight: "900" },
  positive: { color: colors.success, fontWeight: "900" },
  negative: { color: colors.danger, fontWeight: "900" },
  selectedLocation: { backgroundColor: colors.secondary, borderColor: colors.primary, borderRadius: radii.md, borderWidth: 1, padding: spacing.md },
  selectedLocationText: { color: colors.primary, fontWeight: "900" },
  validationReason: { color: colors.textSecondary, fontSize: 13, marginTop: spacing.xs },
  flex: { flex: 1 },
  sectionHeading: { color: colors.text, fontSize: 13, fontWeight: "900", marginTop: spacing.sm },
});
