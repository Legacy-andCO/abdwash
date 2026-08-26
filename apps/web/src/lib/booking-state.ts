import type { Availability, Booking, Catalogue, Contact, CustomerProfileBootstrap, CustomerSavedAddress, CustomerSavedVehicle, Hold, Location, Vehicle } from "./types";
import { coordinatesAreValid, isSupportedGoogleMapsUrl, type Coordinates } from "./location";
import { normalizePhone } from "./phone";
import type { TranslationKey } from "./i18n";

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
  customerProfile: CustomerProfileBootstrap | null;
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
  customerProfile: null,
};

export type BookingAction =
  | { type: "catalogue"; value: Catalogue }
  | { type: "customer_bootstrap"; value: CustomerProfileBootstrap }
  | { type: "saved_location"; value: CustomerSavedAddress }
  | { type: "saved_vehicle"; value: CustomerSavedVehicle }
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
    case "customer_bootstrap": {
      const profile = action.value.profile;
      const defaultAddress = action.value.addresses.find((address) => address.is_default);
      return {
        ...state,
        customerProfile: action.value,
        contact: profile ? { ...state.contact, first_name: profile.first_name, surname: profile.surname, email: action.value.authenticated_email, phone: profile.phone } : { ...state.contact, email: action.value.authenticated_email },
        location: defaultAddress ? { written_address: defaultAddress.written_address, location_url: defaultAddress.location_url, latitude: defaultAddress.latitude, longitude: defaultAddress.longitude, instructions: defaultAddress.location_instructions ?? "" } : state.location,
      };
    }
    case "saved_location": return { ...state, location: { written_address: action.value.written_address, location_url: action.value.location_url, latitude: action.value.latitude, longitude: action.value.longitude, instructions: action.value.location_instructions ?? "" } };
    case "saved_vehicle": return { ...state, vehicles: [{ key: emptyVehicle().key, vehicle_id: action.value.id, make: action.value.make, model: action.value.model, year: action.value.year?.toString() ?? "", vehicle_type: action.value.vehicle_type, colour: action.value.colour ?? "", plate_number: action.value.plate_number ?? "", notes: action.value.notes ?? "", service_id: state.defaultServiceId }, ...state.vehicles.filter((vehicle) => (vehicle.make || vehicle.model) && vehicle.vehicle_id !== action.value.id)], availability: null, selectedSlotTime: "", hold: null };
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

type ErrorTranslator = (key: TranslationKey) => string;

function errorMessage(t: ErrorTranslator | undefined, key: TranslationKey, fallback: string): string {
  return t ? t(key) : fallback;
}

export function contactErrors(contact: Contact, location: Location, t?: ErrorTranslator): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!contact.first_name.trim()) errors.first_name = errorMessage(t, "booking.validation.firstName", "Enter your first name.");
  if (!contact.surname.trim()) errors.surname = errorMessage(t, "booking.validation.surname", "Enter your surname.");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) errors.email = errorMessage(t, "booking.validation.email", "Enter a valid email address.");
  if (!normalizePhone(contact.phone, contact.phone_country)) errors.phone = errorMessage(t, "booking.validation.phone", "Enter a valid international phone number.");
  if (location.written_address.trim().length < 5) errors.written_address = errorMessage(t, "booking.validation.address", "Enter the service address.");
  if (location.instructions.trim().length < 2) errors.instructions = errorMessage(t, "booking.validation.locationNotes", "Add location notes so our team can find you.");
  if (!isSupportedGoogleMapsUrl(location.location_url)) errors.location_url = errorMessage(t, "booking.validation.mapsUrl", "Select a location or paste a supported Google Maps link.");
  const hasLatitude = location.latitude !== null;
  const hasLongitude = location.longitude !== null;
  if (hasLatitude !== hasLongitude) errors.location = errorMessage(t, "booking.validation.location", "Select the service location again.");
  if (hasLatitude && hasLongitude && !coordinatesAreValid({ latitude: location.latitude!, longitude: location.longitude! })) errors.location = errorMessage(t, "booking.validation.location", "Select a valid service location.");
  return errors;
}

export function vehicleErrors(vehicles: Vehicle[], t?: ErrorTranslator): Record<string, string> {
  const errors: Record<string, string> = {};
  vehicles.forEach((vehicle) => {
    if (!vehicle.make.trim()) errors[`${vehicle.key}.make`] = errorMessage(t, "booking.validation.make", "Enter the make.");
    if (!vehicle.model.trim()) errors[`${vehicle.key}.model`] = errorMessage(t, "booking.validation.model", "Enter the model.");
    if (!vehicle.vehicle_type.trim()) errors[`${vehicle.key}.vehicle_type`] = errorMessage(t, "booking.validation.vehicleType", "Choose a type.");
    if (vehicle.plate_number.trim().length < 2) errors[`${vehicle.key}.plate_number`] = errorMessage(t, "booking.validation.plate", "Enter the plate number.");
    if (!vehicle.service_id) errors[`${vehicle.key}.service_id`] = errorMessage(t, "booking.validation.service", "Choose a service.");
    if (vehicle.year && (+vehicle.year < 1900 || +vehicle.year > 2200)) errors[`${vehicle.key}.year`] = errorMessage(t, "booking.validation.year", "Enter a valid year.");
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
