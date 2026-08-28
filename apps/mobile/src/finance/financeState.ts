export const expenseCategories = [
  "chemicals_supplies",
  "fuel",
  "vehicle_transport",
  "equipment",
  "maintenance_repairs",
  "staff",
  "marketing",
  "rent_utilities",
  "software_subscriptions",
  "government_fees",
  "professional_services",
  "miscellaneous",
] as const;

export function expenseAmountMinor(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return Math.round(parsed * 100);
}

export function cashDifference(expectedMinor: number, declaredMinor: number) {
  return declaredMinor - expectedMinor;
}

export function cashDifferenceLabel(differenceMinor: number) {
  return differenceMinor === 0
    ? ("exact" as const)
    : differenceMinor < 0
      ? ("short" as const)
      : ("over" as const);
}

export function canConfirmCashHandover(
  paymentCount: number,
  declaredMinor: number,
  differenceMinor: number,
  note: string,
) {
  return (
    paymentCount > 0 &&
    Number.isFinite(declaredMinor) &&
    declaredMinor >= 0 &&
    (differenceMinor === 0 || Boolean(note.trim()))
  );
}
