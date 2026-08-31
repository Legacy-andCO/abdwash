import type { CountryCode } from "libphonenumber-js/min";

export type Service = {
  id: string;
  name: string;
  description: string | null;
  price_minor: number;
  currency_code: string;
  estimated_duration_minutes: number;
  mobile_available?: boolean;
  shop_available?: boolean;
  included_features?: string[];
  product_kind?: "single_service" | "monthly_package";
  customer_bookable?: boolean;
  prices?: { vehicle_type: string; price_minor: number }[];
  addons?: ServiceAddon[];
};

export type ServiceAddon = {
  id: string;
  name: string;
  description: string | null;
  price_minor: number;
  currency_code: string;
  default_duration_minutes: number;
  mobile_available: boolean;
  shop_available: boolean;
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
  mobile_minimum_enabled?: boolean;
  mobile_minimum_minor?: number;
};

export type Catalogue = {
  business_name: string;
  settings: BusinessSettings;
  services: Service[];
};

export type AvailabilitySlot = {
  time: string;
  starts_at: string;
  ends_at: string;
  available: boolean;
  required_slot_count: number;
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
export type BillingDetails = {
  company_name: string;
  billing_address: string;
  tax_registration_number: string;
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
  vehicle_id?: string;
  make: string;
  model: string;
  year: string;
  vehicle_type: string;
  colour: string;
  plate_number: string;
  notes: string;
  service_id: string;
  addon_ids?: string[];
  loyalty_reward_id?: string;
};

export type LoyaltyRewardService = { id: string; name: string };
export type LoyaltySummary = {
  enabled: boolean;
  configured: boolean;
  required_washes: number;
  progress_washes: number;
  washes_remaining: number;
  lifetime_qualifying_washes: number;
  available_rewards: number;
  reserved_rewards: number;
  redeemed_rewards: number;
  reward_service: LoyaltyRewardService | null;
  rewards: {
    id: string;
    service: LoyaltyRewardService;
    list_price_minor: number;
    status: "available" | "reserved" | "redeemed";
    created_at: string;
    reserved_at: string | null;
    redeemed_at: string | null;
  }[];
  history: {
    id: string;
    event_type: string;
    quantity: number;
    reason: string | null;
    booking_reference: string | null;
    vehicle_label: string | null;
    created_at: string;
  }[];
};

export type CustomerProfile = {
  id: string;
  first_name: string;
  surname: string;
  email: string;
  phone: string;
};
export type CustomerSavedAddress = {
  id: string;
  label: string;
  written_address: string;
  location_url: string;
  latitude: number | null;
  longitude: number | null;
  location_instructions: string | null;
  is_default: boolean;
};
export type CustomerSavedVehicle = {
  id: string;
  make: string;
  model: string;
  year: number | null;
  vehicle_type: string;
  colour: string | null;
  plate_number: string | null;
  notes: string | null;
};
export type CustomerProfileBootstrap = {
  authenticated_email: string;
  profile: CustomerProfile | null;
  addresses: CustomerSavedAddress[];
  vehicles: CustomerSavedVehicle[];
  loyalty?: LoyaltySummary | null;
};

export type BookingVehicleSummary = {
  make: string;
  model: string;
  year: number | null;
  vehicle_type: string;
  colour: string | null;
  plate_number: string | null;
  service_name: string;
  service_id?: string | null;
  line_total_minor: number;
  list_price_minor?: number | null;
  discount_minor?: number;
  discount_type?: string | null;
  loyalty_reward_id?: string | null;
  expected_duration_minutes?: number | null;
  addons?: {
    id?: string | null;
    name: string;
    price_minor: number;
    expected_duration_minutes: number;
  }[];
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
  customer_first_name: string;
  customer_surname: string;
  written_address: string;
  location_url: string;
  location_instructions: string | null;
  vehicles: BookingVehicleSummary[];
  management_token: string;
};

export type RevenueInvoice = {
  id: string;
  invoice_number: string;
  document_type: "tax_invoice" | "invoice";
  issued_at: string;
  supply_date: string;
  booking_reference: string;
  currency_code: string;
  supplier: Record<string, unknown>;
  customer: Record<string, unknown>;
  lines: {
    description: string;
    quantity: number;
    unit_price_minor: number;
    discount_minor: number;
    line_total_minor: number;
    vehicle: string | null;
  }[];
  subtotal_minor: number;
  discount_minor: number;
  vat_amount_minor: number;
  total_minor: number;
  payment_method: string;
  payment_reference: string | null;
};

export type ManagedBooking = Omit<
  Booking,
  "id" | "vehicle_count" | "management_token"
> & {
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
