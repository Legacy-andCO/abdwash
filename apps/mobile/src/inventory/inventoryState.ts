export const inventoryCategories = [
  "chemicals",
  "cleaning_products",
  "microfibers_towels",
  "brushes",
  "pads",
  "bottles_sprayers",
  "ppe",
  "disposable_consumables",
  "equipment_consumables",
  "other",
] as const;

export const inventoryUnits = [
  "piece",
  "liter",
  "milliliter",
  "kilogram",
  "gram",
  "meter",
  "roll",
  "box",
  "pack",
] as const;

export type InventoryAction =
  | "create_item"
  | "edit_item"
  | "create_location"
  | "receive"
  | "transfer"
  | "usage"
  | "wastage"
  | "stock_count";

export type InventoryActionValidation = {
  canSubmit: boolean;
  reason: string | null;
};

export function getInventoryActionValidation(
  action: InventoryAction,
  input: {
    name: string;
    threshold: string;
    itemId: string;
    locationId: string;
    destinationId: string;
    hasQuantityLine: boolean;
    reason: string;
    jobId: string;
    expenseAmount: string;
    isEmployee: boolean;
  },
): InventoryActionValidation {
  if (action === "create_item" || action === "edit_item") {
    if (!input.name.trim()) return invalid("Enter an item name.");
    if (!validQuantity(input.threshold, true))
      return invalid("Enter a valid low-stock threshold.");
    return valid();
  }
  if (action === "create_location") {
    return input.name.trim() ? valid() : invalid("Enter a location name.");
  }
  if (!input.locationId) return invalid("Select a stock location.");
  if (!input.itemId) return invalid("Select an inventory item.");
  if (!input.hasQuantityLine)
    return invalid(
      action === "stock_count"
        ? "Enter a valid counted quantity."
        : "Enter a quantity greater than zero.",
    );
  if (action === "transfer") {
    if (!input.destinationId) return invalid("Select a destination location.");
    if (input.destinationId === input.locationId)
      return invalid("Source and destination must be different.");
  }
  if ((action === "wastage" || action === "stock_count") && !input.reason.trim())
    return invalid("Enter a reason.");
  if (action === "usage" && input.isEmployee && !input.jobId.trim())
    return invalid("Enter the assigned job ID.");
  if (
    action === "receive" &&
    input.expenseAmount.trim() &&
    !validQuantity(input.expenseAmount)
  )
    return invalid("Enter a valid purchase total or leave it empty.");
  return valid();
}

function valid(): InventoryActionValidation {
  return { canSubmit: true, reason: null };
}

function invalid(reason: string): InventoryActionValidation {
  return { canSubmit: false, reason };
}

export function inventoryStatus(quantity: number, threshold: number) {
  if (quantity <= 0) return "out" as const;
  if (quantity <= threshold) return "low" as const;
  return "normal" as const;
}

export function quantityLabel(quantity: number, unit: string) {
  return `${Number(quantity).toLocaleString(undefined, { maximumFractionDigits: 3 })} ${unit}`;
}

export function validQuantity(value: string, allowZero = false) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && (allowZero ? parsed >= 0 : parsed > 0);
}

export function managementInventoryActions(role: string): InventoryAction[] {
  return role === "manager" || role === "admin"
    ? [
        "create_item",
        "create_location",
        "receive",
        "transfer",
        "usage",
        "wastage",
        "stock_count",
      ]
    : ["usage"];
}
