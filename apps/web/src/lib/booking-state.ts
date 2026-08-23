import type { Availability, Booking, Catalogue, Contact, Hold, Location, Vehicle } from "./types";
import { coordinatesAreValid, isSupportedGoogleMapsUrl, type Coordinates } from "./location";
import { normalizePhone } from "./phone";

export const steps = ["service", "details", "vehicles", "review", "schedule", "payment", "confirmation"] as const;
export type BookingStep = (typeof steps)[number];

export type BookingState = {
  step: BookingStep;
  catalogue: Catalogue | null;
  defaultServiceId: string;
  contact: Contact;
  location: Location;
  vehicles: Vehicle[];
  selectedDate: string;
  availability: Availability | null;
  selectedSlotTime: string;
  hold: Hold | null;
  booking: Booking | null;
};

export const emptyVehicle = (serviceId = ""): Vehicle => ({
  key: globalThis.crypto?.randomUUID?.() ?? `vehicle-${Date.now()}-${Math.random()}`,
  make: "",
  model: "",
  year: "",
  vehicle_type: "",
  colour: "",
  plate_number: "",
  notes: "",
  service_id: serviceId,
});

export const initialBookingState: BookingState = {
  step: "service",
  catalogue: null,
  defaultServiceId: "",
  contact: { first_name: "", surname: "", email: "", phone: "", phone_country: "AE" },
  location: { written_address: "", location_url: "", latitude: null, longitude: null, instructions: "" },
  vehicles: [emptyVehicle()],
  selectedDate: "",
  availability: null,
  selectedSlotTime: "",
  hold: null,
  booking: null,
};

export type BookingAction =
  | { type: "catalogue"; value: Catalogue }
  | { type: "step"; value: BookingStep }
  | { type: "service"; value: string }
  | { type: "contact"; field: keyof Contact; value: string }
  | { type: "location"; field: "written_address" | "location_url" | "instructions"; value: string }
  | { type: "manual_location_url"; value: string }
  | { type: "location_coordinates"; value: Coordinates; writtenAddress?: string }
  | { type: "vehicle"; key: string; field: keyof Vehicle; value: string }
  | { type: "add_vehicle" }
  | { type: "remove_vehicle"; key: string }
  | { type: "date"; value: string }
  | { type: "availability"; value: Availability | null }
  | { type: "slot"; value: string }
  | { type: "hold"; value: Hold | null }
  | { type: "booking"; value: Booking };

export function bookingReducer(state: BookingState, action: BookingAction): BookingState {
  switch (action.type) {
    case "catalogue": {
      const first = action.value.services[0]?.id ?? "";
      return {
        ...state,
        catalogue: action.value,
        defaultServiceId: state.defaultServiceId || first,
        vehicles: state.vehicles.map((vehicle) => ({ ...vehicle, service_id: vehicle.service_id || first })),
      };
    }
    case "step": return { ...state, step: action.value };
    case "service": return {
      ...state,
      defaultServiceId: action.value,
      vehicles: state.vehicles.map((vehicle, index) => index === 0 ? { ...vehicle, service_id: action.value } : vehicle),
    };
    case "contact": return { ...state, contact: { ...state.contact, [action.field]: action.value } };
    case "location": return { ...state, location: { ...state.location, [action.field]: action.value } };
    case "manual_location_url": return {
      ...state,
      location: {
        ...state.location,
        location_url: action.value,
        latitude: null,
        longitude: null,
      },
    };
    case "location_coordinates": return {
      ...state,
      location: {
        ...state.location,
        written_address: action.writtenAddress || state.location.written_address,
        latitude: action.value.latitude,
        longitude: action.value.longitude,
        location_url: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${action.value.latitude},${action.value.longitude}`)}`,
      },
    };
    case "vehicle": return {
      ...state,
      vehicles: state.vehicles.map((vehicle) => vehicle.key === action.key ? { ...vehicle, [action.field]: action.value } : vehicle),
      availability: null,
      selectedSlotTime: "",
      hold: null,
    };
    case "add_vehicle": return { ...state, vehicles: [...state.vehicles, emptyVehicle(state.defaultServiceId)], availability: null, selectedSlotTime: "", hold: null };
    case "remove_vehicle": return { ...state, vehicles: state.vehicles.filter((vehicle) => vehicle.key !== action.key), availability: null, selectedSlotTime: "", hold: null };
    case "date": return { ...state, selectedDate: action.value, availability: null, selectedSlotTime: "", hold: null };
    case "availability": return { ...state, availability: action.value, selectedSlotTime: "", hold: null };
    case "slot": return { ...state, selectedSlotTime: action.value, hold: null };
    case "hold": return { ...state, hold: action.value };
    case "booking": return { ...state, booking: action.value, step: "confirmation" };
  }
}

export function contactErrors(contact: Contact, location: Location): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!contact.first_name.trim()) errors.first_name = "Enter your first name.";
  if (!contact.surname.trim()) errors.surname = "Enter your surname.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) errors.email = "Enter a valid email address.";
  if (!normalizePhone(contact.phone, contact.phone_country)) errors.phone = "Enter a valid international phone number.";
  if (location.written_address.trim().length < 5) errors.written_address = "Enter the service address.";
  if (!isSupportedGoogleMapsUrl(location.location_url)) errors.location_url = "Select a location or paste a supported Google Maps link.";
  const hasLatitude = location.latitude !== null;
  const hasLongitude = location.longitude !== null;
  if (hasLatitude !== hasLongitude) errors.location = "Select the service location again.";
  if (hasLatitude && hasLongitude && !coordinatesAreValid({ latitude: location.latitude!, longitude: location.longitude! })) errors.location = "Select a valid service location.";
  return errors;
}

export function vehicleErrors(vehicles: Vehicle[]): Record<string, string> {
  const errors: Record<string, string> = {};
  vehicles.forEach((vehicle) => {
    if (!vehicle.make.trim()) errors[`${vehicle.key}.make`] = "Enter the make.";
    if (!vehicle.model.trim()) errors[`${vehicle.key}.model`] = "Enter the model.";
    if (!vehicle.vehicle_type.trim()) errors[`${vehicle.key}.vehicle_type`] = "Choose a type.";
    if (!vehicle.service_id) errors[`${vehicle.key}.service_id`] = "Choose a service.";
    if (vehicle.year && (+vehicle.year < 1900 || +vehicle.year > 2200)) errors[`${vehicle.key}.year`] = "Enter a valid year.";
  });
  return errors;
}

export function calculateEstimate(vehicles: Vehicle[], catalogue: Catalogue): number {
  const prices = new Map(catalogue.services.map((service) => [service.id, service.price_minor]));
  return vehicles.reduce((total, vehicle) => total + (prices.get(vehicle.service_id) ?? 0), 0);
}

export function canSubmitPayment(choice: "pay_after_service" | "pay_now"): boolean {
  return choice === "pay_after_service";
}
