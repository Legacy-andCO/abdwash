export function hourlyQuickTimes(
  openingTime?: string | null,
  closingTime?: string | null,
  durationMinutes = 0,
): string[] {
  if (!openingTime || !closingTime) return [];
  const [openHour, openMinute] = openingTime.split(":").map(Number);
  const [closeHour, closeMinute] = closingTime.split(":").map(Number);
  if (
    [openHour, openMinute, closeHour, closeMinute].some(
      (value) => !Number.isFinite(value),
    )
  ) {
    return [];
  }
  const opening = openHour * 60 + openMinute;
  const closing = closeHour * 60 + closeMinute;
  const firstHour = Math.ceil(opening / 60) * 60;
  const values: string[] = [];
  for (
    let minutes = firstHour;
    minutes + Math.max(0, durationMinutes) <= closing;
    minutes += 60
  ) {
    values.push(
      `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`,
    );
  }
  return values;
}
