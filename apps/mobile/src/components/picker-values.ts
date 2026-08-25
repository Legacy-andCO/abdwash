export function toIsoDate(value: Date): string {
  return [
    value.getFullYear(),
    String(value.getMonth() + 1).padStart(2, "0"),
    String(value.getDate()).padStart(2, "0"),
  ].join("-");
}

export function fromIsoDate(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return year && month && day ? new Date(year, month - 1, day, 12) : new Date();
}

export function toApiTime(value: Date): string {
  return `${String(value.getHours()).padStart(2, "0")}:${String(value.getMinutes()).padStart(2, "0")}`;
}

export function fromApiTime(value: string): Date {
  const [hour, minute] = value.split(":").map(Number);
  const result = new Date();
  result.setHours(hour || 0, minute || 0, 0, 0);
  return result;
}

export function formatHumanDate(value: string): string {
  return fromIsoDate(value).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatHumanTime(value: string): string {
  return fromApiTime(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
