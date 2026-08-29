import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("inventory mobile contract", () => {
  it("keeps Inventory within two taps without adding a bottom tab", () => {
    const shell = source("./navigation/OperationsShell.tsx");
    const reports = source("./screens/ReportsScreen.tsx");
    const today = source("./screens/TodayScreen.tsx");
    expect(shell).toContain("<InventoryScreen");
    expect(reports).toContain('title="Open Inventory"');
    expect(today).toContain('title="Open Inventory"');
    expect(source("./operations.ts")).not.toContain('"inventory"');
  });

  it("provides overview, stock, movement, and task-oriented controls", () => {
    const screen = source("./screens/InventoryScreen.tsx");
    expect(screen).toContain(
      'type InventoryTab = "overview" | "catalogue" | "stock" | "movements"',
    );
    expect(screen).toContain('create_item: "Create item"');
    expect(screen).toContain('receive: "Receive stock"');
    expect(screen).toContain('transfer: "Transfer"');
    expect(screen).toContain('wastage: "Record wastage"');
    expect(screen).toContain('stock_count: "Stock count"');
  });

  it("uses coarse stock operations with one shared retry-safe event store", () => {
    const queries = source("./queries/operations.ts");
    const api = source("./lib.ts");
    expect(queries).toContain("new ClientEventIdStore()");
    expect(queries).toContain("eventIds.failed(key, error)");
    expect(api).toContain('"/api/v1/staff/inventory/receipts"');
    expect(api).toContain('"/api/v1/staff/inventory/transfers"');
    expect(api).toContain('"/api/v1/staff/inventory/stock-counts"');
  });

  it("stages multiple items into one batch mutation", () => {
    const screen = source("./screens/InventoryScreen.tsx");
    expect(screen).toContain('title="Add another item"');
    expect(screen).toContain("const submittedLines = draftLines.length");
    expect(screen).toContain("lines: quantityLines");
  });

  it("scopes and persists inventory cache families independently", () => {
    const policy = source("./cache/policy.ts");
    const sync = source("./cache/sync.ts");
    expect(policy).toContain('"inventory-stock", scope');
    expect(policy).toContain('"inventory-movements", scope');
    expect(sync).toContain("inventory: [");
    expect(sync).toContain('"inventory-attention"');
    expect(sync).toContain('"team-stock"');
  });

  it("invalidates finance only when a receipt records an expense", () => {
    const queries = source("./queries/operations.ts");
    expect(queries).toContain('input.action === "receive"');
    expect(queries).toContain("record_as_expense");
    expect(queries).toContain('queryKey: ["finance", scope]');
  });

  it("shows the active location and explains every disabled action", () => {
    const screen = source("./screens/InventoryScreen.tsx");
    expect(screen).toContain("getInventoryActionValidation");
    expect(screen).toContain("{locations[0].name} ✓");
    expect(screen).toContain("validation.reason");
    expect(screen).toContain('accessibilityRole="alert"');
  });

  it("provides role-appropriate recovery when no stock location exists", () => {
    const screen = source("./screens/InventoryScreen.tsx");
    expect(screen).toContain("No stock location is configured.");
    expect(screen).toContain('title="Create Main Shop Location"');
    expect(screen).toContain("Ask a manager to configure an inventory location.");
  });

  it("shows compact stock in Team Detail", () => {
    const team = source("./screens/TeamScreen.tsx");
    expect(team).toContain("useTeamStockSummaryQuery");
    expect(team).toContain("No linked stock location");
    expect(team).toContain("stock.low_stock_count");
  });

  it("shows completion discrepancies in the existing Inventory manager area", () => {
    const screen = source("./screens/InventoryScreen.tsx");
    const api = source("./lib.ts");
    expect(screen).toContain("useInventoryAttentionQuery");
    expect(screen).toContain('label="Needs review"');
    expect(screen).toContain('title="Open job"');
    expect(screen).toContain('title="Stock count"');
    expect(screen).toContain('title="Mark reviewed"');
    expect(api).toContain('"/api/v1/staff/inventory/consumption/attention"');
    expect(api).toContain("reviewInventoryConsumption");
  });

  it("keeps automatic consumption and direct expenses inside Job Detail", () => {
    const jobs = source("./screens/JobsScreen.tsx");
    expect(jobs).toContain("job.consumption");
    expect(jobs).toContain("Expected {line.expected_quantity}");
    expect(jobs).toContain("Recorded {Number(line.automatic_applied_quantity)");
    expect(jobs).toContain("Additional manual usage");
    expect(jobs).toContain("DIRECT EXPENSES");
    expect(jobs).toContain("useExpenseMutation");
    expect(jobs).toContain("Inventory needs manager review.");
  });

  it("describes templates as completion-time expected usage and exposes inactive lines", () => {
    const services = source("./screens/ServicesPricingScreen.tsx");
    expect(services).toContain("Expected standard quantities are snapshotted at job completion");
    expect(services).toContain('useInventoryItemsQuery(context, "", 0, true)');
    expect(services).toContain("inactive; remove before saving");
    expect(services).not.toContain("stock is not deducted automatically");
  });

  it("invalidates only the inventory resources affected by completion", () => {
    const queries = source("./queries/operations.ts");
    const completion = queries.slice(
      queries.indexOf("export function useJobActionMutation"),
      queries.indexOf("export function useCashPaymentMutation"),
    );
    expect(completion).toContain('action === "complete"');
    expect(completion).toContain("queryKeys.inventoryOverview(scope)");
    expect(completion).toContain("queryKeys.inventoryAttention(scope)");
    expect(completion).toContain('queryKey: ["inventory-stock", scope]');
    expect(completion).not.toContain('queryKey: ["finance", scope]');
    expect(completion).not.toContain('queryKey: ["customers", scope]');
    expect(completion).not.toContain('queryKey: ["teams", scope]');
  });
});
