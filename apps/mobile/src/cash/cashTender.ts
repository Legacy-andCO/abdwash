export type CashTenderCalculation = {
  tenderedMinor: number;
  changeMinor: number;
  valid: boolean;
  error: string | null;
};

export function parseMoneyToMinor(value: string): number | null {
  const normalized = value.trim().replaceAll(",", "");
  if (!/^\d+(?:\.\d{0,2})?$/.test(normalized)) return null;
  const [whole, fraction = ""] = normalized.split(".");
  const minor = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(minor) ? minor : null;
}

export function calculateCashTender(
  dueMinor: number,
  received: string,
): CashTenderCalculation {
  const tenderedMinor = parseMoneyToMinor(received);
  if (tenderedMinor === null)
    return {
      tenderedMinor: 0,
      changeMinor: 0,
      valid: false,
      error: "Enter a valid cash amount with no more than two decimal places.",
    };
  if (tenderedMinor < dueMinor)
    return {
      tenderedMinor,
      changeMinor: 0,
      valid: false,
      error: "Amount received is less than the amount due.",
    };
  return {
    tenderedMinor,
    changeMinor: tenderedMinor - dueMinor,
    valid: true,
    error: null,
  };
}

export function minorToInput(minor: number): string {
  return `${Math.floor(minor / 100)}.${String(minor % 100).padStart(2, "0")}`;
}

export function formatMoney(currency: string, minor: number): string {
  return `${currency} ${minorToInput(minor)}`;
}
