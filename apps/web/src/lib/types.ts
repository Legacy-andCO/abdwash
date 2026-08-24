import type { CountryCode } from "libphonenumber-js/min";

export type Service = {
  id: string;
  name: string;
  description: string | null;
  price_minor: number;
  currency_code: string;
  estimated_duration_minutes: number;
};

export type BusinessSettings = {
  timezone: string;
  currency_code: string;
  opening_time: string;
  closing_time: string;
  slot_duration_minutes: number;
  multi_vehicle_threshold: number;
  multi_vehicle_required_slots: number;
  hold_duration_minutes: number;
  cancellation_cutoff_hours: number;
};

export type Catalogue = {
  business_name: string;
  settings: BusinessSettings;
  services: Service[];
};

export type AvailabilityResource = { resource_id: string; resource_name: string };

export type AvailabilitySlot = {
  time: string;
  starts_at: string;
  ends_at: string;
  available: boolean;
  required_slot_count: number;
  resources: AvailabilityResource[];
  unavailable_reason: string | null;
};

export type Availability = {
  date: string;
  timezone: string;
  vehicle_count: number;
  required_slot_count: number;
  slots: AvailabilitySlot[];
};

export type Hold = {
  hold_token: string;
  resource_id: string;
  starts_at: string;
  ends_at: string;
  expires_at: string;
  required_slot_count: number;
};

export type Contact = {
  first_name: string;
  surname: string;
  email: string;
  phone: string;
  phone_country: CountryCode;
};
export type Location = {
  written_address: string;
  location_url: string;
  latitude: number | null;
  longitude: number | null;
  instructions: string;
};

export type Vehicle = {
  key: string;
  make: string;
  model: string;
  year: string;
  vehicle_type: string;
  colour: string;
  plate_number: string;
  notes: string;
  service_id: string;
};

export type BookingVehicleSummary = {
  make: string;
  model: string;
  year: number | null;
  vehicle_type: string;
  colour: string | null;
  plate_number: string | null;
  service_name: string;
  line_total_minor: number;
};

export type Booking = {
  id: string;
  reference: string;
  status: string;
  payment_choice: string;
  payment_status: string;
  scheduled_start: string;
  scheduled_end: string;
  vehicle_count: number;
  total_amount_minor: number;
  currency_code: string;
  resource_id: string;
  customer_first_name: string;
  customer_surname: string;
  written_address: string;
  location_url: string;
  location_instructions: string | null;
  vehicles: BookingVehicleSummary[];
  management_token: string;
};

export type ManagedBooking = Omit<Booking, "id" | "vehicle_count" | "resource_id" | "management_token"> & {
  cancellation_eligible: boolean;
  cancellation_cutoff_at: string;
  cancellation_status: string | null;
  timezone: string;
};

export type CustomerBookingStatus = {
  key: string;
  label: string;
  stage: number;
  job_status: string | null;
};

export type CustomerBookingSummary = {
  id: string;
  reference: string;
  status: CustomerBookingStatus;
  payment_status: string;
  scheduled_start: string;
  scheduled_end: string;
  vehicle_count: number;
  total_amount_minor: number;
  currency_code: string;
  written_address: string;
  vehicles: BookingVehicleSummary[];
  created_at: string;
  cancellation_eligible: boolean;
  reschedule_eligible: boolean;
  estimated_arrival_at: string | null;
  category: "upcoming" | "past" | "cancelled";
};

export type CustomerBookingDetail = CustomerBookingSummary & {
  payment_choice: string;
  payment_status: string;
  location_url: string;
  location_instructions: string | null;
  latitude: number | null;
  longitude: number | null;
  cancellation_cutoff_at: string;
  cancellation_status: string | null;
  timezone: string;
};

export type CustomerContext = {
  profile: null | {
    id: string;
    first_name: string;
    surname: string;
    email: string;
    phone: string;
  };
  booking_count: number;
};
