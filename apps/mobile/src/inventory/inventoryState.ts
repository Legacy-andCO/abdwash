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
