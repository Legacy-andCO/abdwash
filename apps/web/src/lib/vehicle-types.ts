export const VEHICLE_TYPES = [
  "sedan",
  "suv",
  "hatchback",
  "coupe",
  "pickup",
  "van",
  "other",
] as const;

export type VehicleType = (typeof VEHICLE_TYPES)[number];

export function isVehicleType(value: string): value is VehicleType {
  return (VEHICLE_TYPES as readonly string[]).includes(value);
}
