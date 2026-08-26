export function normalizeCustomerSearch(value: string) {
  return value.trim().replace(/\s+/g, " ");
}
