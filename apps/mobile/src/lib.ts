import * as SecureStore from "expo-secure-store";
import { createClient, type Session } from "@supabase/supabase-js";
import "react-native-url-polyfill/auto";
import type { Role } from "./capabilities";
import { ApiError } from "./errors/domainErrors";
import { parseApiErrorPayload } from "./errors/parseApiError";
import { RequestTimedOut, withRequestTimeout } from "./network/requestTimeout";
import { beginTrackedWrite } from "./network/writeRegistry";
import { reportTripDiagnostic } from "./location/tripDiagnostics";

const apiUrl = (
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "",
  {
    auth: {
      storage: {
        getItem: SecureStore.getItemAsync,
        setItem: SecureStore.setItemAsync,
        removeItem: SecureStore.deleteItemAsync,
      },
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  },
);

export type { Role } from "./capabilities";
export type StaffContext = {
  staff_id: string;
  business_id: string;
  business_name: string;
  role: Role;
  timezone: string;
  display_name: string;
  username: string;
  phone: string | null;
  must_change_password: boolean;
};
export type TeamRef = { id: string; name: string };
export type Profile = {
  id: string;
  display_name: string;
  username: string;
  phone: string | null;
  role: Role;
  is_active: boolean;
  must_change_password: boolean;
  teams: TeamRef[];
};
export type JobTimelineEvent = {
  id: string;
  occurred_at: string;
  event: string;
  actor: string | null;
  detail: string | null;
};
export type Job = {
  id: string;
  booking_id: string;
  booking_reference: string;
  assigned_staff_id: string | null;
  assigned_staff_name: string | null;
  assigned_team_id: string | null;
  assigned_team_name: string | null;
  status: string;
  scheduled_start: string;
  scheduled_end: string;
  en_route_at: string | null;
  estimated_arrival_at: string | null;
  arrived_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  customer_name: string;
  customer_phone: string;
  written_address: string;
  location_url: string;
  latitude: number | null;
  longitude: number | null;
  location_instructions: string | null;
  payment_status: string;
  payment_method: string | null;
  total_amount_minor: number;
  currency_code: string;
  vehicles: {
    make: string;
    model: string;
    year: number | null;
    vehicle_type: string;
    colour: string | null;
    plate_number: string | null;
    notes: string | null;
    service_name: string;
    amount_minor: number;
  }[];
  timeline: JobTimelineEvent[];
};
export type Team = {
  id: string;
  name: string;
  is_active: boolean;
  member_count: number;
  jobs_today: number;
  active_job_reference: string | null;
  active_job_status: string | null;
};
export type TeamDetail = Team & { members: Profile[]; jobs: Job[] };
export type Attendance = {
  id: string;
  staff_id: string;
  staff_name: string;
  clock_in_at: string;
  clock_out_at: string | null;
  worked_minutes: number;
  late_minutes: number;
  status: string;
};
export type AttendanceOverview = {
  staff_id: string;
  staff_name: string;
  status: string;
  shift_name: string | null;
  shift_start: string | null;
  shift_end: string | null;
  clock_in_at: string | null;
  clock_out_at: string | null;
  worked_minutes: number;
  late_minutes: number;
  missed_shift: boolean;
};
export type Shift = {
  id: string;
  name: string;
  start_time: string;
  end_time: string;
  is_active: boolean;
};
export type ShiftAssignment = {
  id: string;
  staff_id: string;
  staff_name: string;
  shift_id: string;
  shift_name: string;
  work_date: string;
  start_time: string;
  end_time: string;
  team_id: string | null;
  team_name: string | null;
};
export type Leave = {
  id: string;
  staff_id: string;
  staff_name: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  reviewed_at: string | null;
  review_note: string | null;
};
export type Report = {
  start_date: string;
  end_date: string;
  bookings: number;
  completed_washes: number;
  booked_sales_minor: number;
  collected_revenue_minor: number;
  outstanding_minor: number;
  average_booking_value_minor: number;
  currency_code: string;
};
export type ReportPoint = {
  date: string;
  booked_sales_minor: number;
  collected_revenue_minor: number;
  jobs: number;
  completed: number;
  cancelled: number;
};
export type Performance = {
  id: string;
  name: string;
  hours_worked: number;
  late_arrivals: number;
  jobs_completed: number;
  average_wash_minutes: number;
  jobs_per_worked_hour: number;
  job_value_handled_minor: number;
};
export type MixRow = {
  key: string;
  label: string;
  count: number;
  amount_minor: number;
  percentage: number;
};
export type TeamPerformance = {
  id: string;
  name: string;
  completed_jobs: number;
  average_wash_minutes: number;
  average_operational_minutes: number;
  job_value_handled_minor: number;
  jobs_per_active_day: number;
};
export type ReportV2 = {
  summary: Report;
  series: ReportPoint[];
  staff_performance: Performance[];
  service_mix: MixRow[];
  payment_mix: MixRow[];
  team_performance: TeamPerformance[];
};
export type Dashboard = {
  date: string;
  currency_code: string;
  metrics: { key: string; label: string; value: number }[];
  attention: { kind: string; count: number; label: string }[];
  active_jobs: Job[];
};
export type Cancellation = {
  id: string;
  booking_id: string;
  booking_reference: string;
  customer_name: string;
  reason: string | null;
  requested_at: string;
  scheduled_start: string;
  payment_status: string;
  status: string;
};
export type AvailabilitySlot = {
  time: string;
  starts_at: string;
  ends_at: string;
  available: boolean;
  required_slot_count: number;
  resources: { resource_id: string; resource_name: string }[];
  unavailable_reason: string | null;
};
export type SyncState = {
  jobs: number;
  workforce: number;
  schedule: number;
  finance: number;
  customers: number;
};
export type CashPaymentResult = {
  job: Job;
  amount_applied_minor: number;
  tendered_minor: number;
  change_minor: number;
};
export type CustomerProfile = {
  id: string;
  first_name: string;
  surname: string;
  email: string;
  phone: string;
};
export type CustomerAddress = {
  id: string;
  label: string;
  written_address: string;
  location_url: string;
  latitude: number | null;
  longitude: number | null;
  location_instructions: string | null;
  is_default: boolean;
};
export type CustomerVehicle = {
  id: string;
  make: string;
  model: string;
  year: number | null;
  vehicle_type: string;
  colour: string | null;
  plate_number: string | null;
  notes: string | null;
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
    status: string;
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
export type ManagerCustomerListItem = CustomerProfile & {
  active_vehicle_count: number;
  booking_count: number;
  latest_booking_at: string | null;
  available_rewards: number;
  loyalty_progress_washes: number;
  loyalty_required_washes: number;
};
export type ManagerCustomerList = {
  customers: ManagerCustomerListItem[];
  next_offset: number | null;
};
export type ManagerCustomerDetail = {
  profile: CustomerProfile;
  addresses: CustomerAddress[];
  vehicles: CustomerVehicle[];
  bookings: {
    id: string;
    reference: string;
    status: string;
    payment_status: string;
    scheduled_start: string;
    total_amount_minor: number;
    currency_code: string;
    vehicle_count: number;
    job_id: string | null;
    job_status: string | null;
    complaint_count: number;
    vehicles: {
      make: string;
      model: string;
      plate_number: string | null;
      service_name: string | null;
    }[];
  }[];
  bookings_next_offset: number | null;
  loyalty: LoyaltySummary;
};
export type LoyaltySettings = {
  enabled: boolean;
  required_washes: number;
  reward_service: LoyaltyRewardService | null;
};
export type ServiceOption = {
  id: string;
  name: string;
  price_minor: number;
  currency_code: string;
};
export type JobInspection = {
  id: string;
  condition_notes: string | null;
  damage_category: string | null;
  damage_notes: string | null;
  completed_by_staff_id: string;
  completed_by_staff_name: string;
  completed_at: string;
};
export type JobChecklistItem = {
  id: string;
  label: string;
  is_required: boolean;
  position: number;
  completed_at: string | null;
  completed_by_staff_id: string | null;
  completed_by_staff_name: string | null;
};
export type JobPhoto = {
  id: string;
  category: "before" | "after" | "damage" | "issue";
  caption: string | null;
  status: "pending" | "ready";
  created_by_staff_id: string;
  created_by_staff_name: string;
  created_at: string;
  access_url: string | null;
};
export type JobQualityIssue = {
  id: string;
  category: string;
  note: string;
  photo_id: string | null;
  created_by_staff_id: string;
  created_by_staff_name: string;
  created_at: string;
};
export type JobComplaint = {
  id: string;
  description: string;
  status: string;
  review_note: string | null;
  created_by_staff_id: string;
  created_by_staff_name: string;
  created_at: string;
  reviewed_by_staff_id: string | null;
  reviewed_by_staff_name: string | null;
  reviewed_at: string | null;
  correction_job_id: string | null;
};
export type JobQuality = {
  job_id: string;
  inspection: JobInspection | null;
  checklist: JobChecklistItem[];
  photos: JobPhoto[];
  issues: JobQualityIssue[];
  complaints: JobComplaint[];
  required_completed: number;
  required_total: number;
  before_photo_count: number;
  after_photo_count: number;
  issue_count: number;
  can_complete: boolean;
};
export type JobPhotoUploadGrant = {
  photo: JobPhoto;
  bucket: string;
  path: string;
  upload_token: string;
  max_bytes: number;
};

const DEFAULT_TIMEOUT_MS = 15_000;
const AVAILABILITY_TIMEOUT_MS = 20_000;

async function token(session?: Session | null): Promise<string | undefined> {
  return (
    session?.access_token ??
    (await supabase.auth.getSession()).data.session?.access_token
  );
}
export async function api<T>(
  path: string,
  init?: RequestInit,
  session?: Session | null,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const headers = new Headers(init?.headers);
  const access = await token(session);
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (init?.body) headers.set("Content-Type", "application/json");
  const trackedWrite =
    init?.method && !["GET", "HEAD", "OPTIONS"].includes(init.method)
      ? beginTrackedWrite()
      : null;
  const isStartTrip = /\/api\/v1\/staff\/jobs\/[^/]+\/start-trip$/.test(path);
  let response: Response;
  try {
    response = await withRequestTimeout(
      (signal) =>
        fetch(`${apiUrl}${path}`, {
          ...init,
          headers,
          signal,
        }),
      trackedWrite?.signal ?? init?.signal,
      timeoutMs,
    );
  } catch (error) {
    if (error instanceof RequestTimedOut) {
      if (isStartTrip)
        reportTripDiagnostic("trip_api_failed", {
          endpoint: path,
          status: 0,
          code: "REQUEST_TIMEOUT",
        });
      throw new ApiError(
        "REQUEST_TIMEOUT",
        0,
        "The request took too long. Please try again.",
        undefined,
        path,
      );
    }
    if (init?.signal?.aborted) throw error;
    if (__DEV__) {
      console.warn("[AbdWash API] request_failed", {
        endpoint: path,
        status: 0,
      });
    }
    if (isStartTrip)
      reportTripDiagnostic("trip_api_failed", {
        endpoint: path,
        status: 0,
        code: "OFFLINE",
      });
    throw new ApiError("OFFLINE", 0, undefined, undefined, path);
  } finally {
    trackedWrite?.release();
  }
  if (!response.ok) {
    const parsed = parseApiErrorPayload(
      await response.json().catch(() => ({})),
      response.status,
    );
    const requestId =
      parsed.requestId ?? response.headers.get("X-Request-ID") ?? undefined;
    if (__DEV__) {
      console.warn("[AbdWash API] response_failed", {
        request_id: requestId,
        endpoint: path,
        status: response.status,
        code: parsed.code,
      });
    }
    if (isStartTrip)
      reportTripDiagnostic("trip_api_failed", {
        request_id: requestId,
        endpoint: path,
        status: response.status,
        code: parsed.code,
      });
    throw new ApiError(
      parsed.code,
      response.status,
      parsed.message,
      requestId,
      path,
    );
  }
  if (isStartTrip)
    reportTripDiagnostic("trip_api_success", {
      request_id: response.headers.get("X-Request-ID") ?? undefined,
      endpoint: path,
      status: response.status,
    });
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
const json = (method: string, body: object): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
const today = () => new Date().toISOString().slice(0, 10);

export const getContext = (session?: Session | null) =>
  api<StaffContext>("/api/v1/staff/context", undefined, session);
export const getProfile = () => api<Profile>("/api/v1/staff/profile");
export const getSyncState = () => api<SyncState>("/api/v1/staff/sync-state");
export const updateProfile = (body: object) =>
  api<Profile>("/api/v1/staff/profile", json("PATCH", body));
export const getStaff = () => api<Profile[]>("/api/v1/staff/users");
export const createStaff = (body: object) =>
  api<Profile>("/api/v1/staff/users", json("POST", body));
export const updateStaff = (id: string, body: object) =>
  api<Profile>(`/api/v1/staff/users/${id}`, json("PATCH", body));
export type StaffPasswordResetResult = {
  must_change_password: boolean;
  temporary_password: string | null;
};
export const resetStaffPassword = (
  id: string,
  body: { mode: "temporary" | "manual"; new_password?: string },
) =>
  api<StaffPasswordResetResult>(
    `/api/v1/staff/users/${id}/password`,
    json("POST", body),
  );
export type JobFilters = {
  view: "today" | "upcoming" | "history" | "unassigned" | "all";
  scope: "my" | "all";
  date?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  team_id?: string;
  employee_id?: string;
  payment_method?: string;
  service_id?: string;
  search?: string;
  offset?: number;
  limit?: number;
};
export async function getJobs(
  filters: JobFilters,
  signal?: AbortSignal,
  session?: Session | null,
) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") params.set(key, String(value));
  });
  const result = await api<{ jobs: Job[]; next_offset: number | null }>(
    `/api/v1/staff/jobs?${params.toString()}`,
    { signal },
    session,
  );
  return result;
}
export const getJob = (jobId: string, signal?: AbortSignal) =>
  api<Job>(`/api/v1/staff/jobs/${jobId}`, { signal });
export const getJobQuality = (jobId: string, signal?: AbortSignal) =>
  api<JobQuality>(`/api/v1/staff/jobs/${jobId}/quality`, { signal });
export const saveJobInspection = (jobId: string, body: object) =>
  api<void>(
    `/api/v1/staff/jobs/${jobId}/quality/inspection`,
    json("PUT", body),
  );
export const saveJobChecklist = (jobId: string, body: object) =>
  api<void>(`/api/v1/staff/jobs/${jobId}/quality/checklist`, json("PUT", body));
export const addJobQualityIssue = (jobId: string, body: object) =>
  api<void>(`/api/v1/staff/jobs/${jobId}/quality/issues`, json("POST", body));
export const requestJobPhotoUpload = (jobId: string, body: object) =>
  api<JobPhotoUploadGrant>(
    `/api/v1/staff/jobs/${jobId}/quality/photos/upload`,
    json("POST", body),
  );
export const completeJobPhotoUpload = (jobId: string, photoId: string) =>
  api<void>(
    `/api/v1/staff/jobs/${jobId}/quality/photos/${photoId}/complete`,
    json("POST", {}),
  );
async function withPhotoUploadTimeout<T>(operation: Promise<T>): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      operation,
      new Promise<T>((_resolve, reject) => {
        timeout = setTimeout(
          () =>
            reject(
              new ApiError(
                "JOB_PHOTO_UPLOAD_TIMEOUT",
                408,
                "The photo upload timed out. Please try again.",
              ),
            ),
          45_000,
        );
      }),
    ]);
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}
export async function uploadJobPhoto(
  jobId: string,
  uri: string,
  category: JobPhoto["category"],
  clientRequestId: string,
  caption?: string,
) {
  const grant = await requestJobPhotoUpload(jobId, {
    category,
    content_type: "image/jpeg",
    caption: caption?.trim() || null,
    client_request_id: clientRequestId,
  });
  const response = await fetch(uri);
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength > grant.max_bytes)
    throw new ApiError(
      "JOB_PHOTO_TOO_LARGE",
      400,
      "The prepared photo is too large to upload.",
    );
  const { error } = await withPhotoUploadTimeout(
    supabase.storage
      .from(grant.bucket)
      .uploadToSignedUrl(grant.path, grant.upload_token, bytes, {
        contentType: "image/jpeg",
        cacheControl: "3600",
      }),
  );
  if (error)
    throw new ApiError(
      "JOB_PHOTO_UPLOAD_FAILED",
      502,
      "The photo upload failed. Please try again.",
    );
  await completeJobPhotoUpload(jobId, grant.photo.id);
  return grant.photo.id;
}
export const createJobComplaint = (jobId: string, description: string) =>
  api<void>(
    `/api/v1/staff/jobs/${jobId}/quality/complaints`,
    json("POST", { description }),
  );
export const reviewJobComplaint = (
  jobId: string,
  complaintId: string,
  body: object,
) =>
  api<void>(
    `/api/v1/staff/jobs/${jobId}/quality/complaints/${complaintId}/review`,
    json("POST", body),
  );
export const mutateJob = (
  jobId: string,
  action: "start-trip" | "arrive" | "start" | "complete",
  body: object,
) => api<Job>(`/api/v1/staff/jobs/${jobId}/${action}`, json("POST", body));
export const recordCashPayment = (jobId: string, body: object) =>
  api<CashPaymentResult>(
    `/api/v1/staff/jobs/${jobId}/cash-payment`,
    json("POST", body),
  );
export const getManagerCustomers = (
  search: string,
  offset: number,
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams({ offset: String(offset), limit: "30" });
  if (search) params.set("search", search);
  return api<ManagerCustomerList>(`/api/v1/staff/customers?${params}`, {
    signal,
  });
};
export const getManagerCustomer = (
  id: string,
  historyOffset: number,
  signal?: AbortSignal,
) =>
  api<ManagerCustomerDetail>(
    `/api/v1/staff/customers/${id}?history_offset=${historyOffset}&history_limit=30`,
    { signal },
  );
export const updateManagerCustomer = (id: string, body: object) =>
  api<ManagerCustomerDetail>(
    `/api/v1/staff/customers/${id}`,
    json("PATCH", body),
  );
export const createManagerCustomerAddress = (
  customerId: string,
  body: object,
) =>
  api<CustomerAddress>(
    `/api/v1/staff/customers/${customerId}/addresses`,
    json("POST", body),
  );
export const updateManagerCustomerAddress = (
  customerId: string,
  addressId: string,
  body: object,
) =>
  api<CustomerAddress>(
    `/api/v1/staff/customers/${customerId}/addresses/${addressId}`,
    json("PATCH", body),
  );
export const deleteManagerCustomerAddress = (
  customerId: string,
  addressId: string,
) =>
  api<void>(`/api/v1/staff/customers/${customerId}/addresses/${addressId}`, {
    method: "DELETE",
  });
export const createManagerCustomerVehicle = (
  customerId: string,
  body: object,
) =>
  api<CustomerVehicle>(
    `/api/v1/staff/customers/${customerId}/vehicles`,
    json("POST", body),
  );
export const updateManagerCustomerVehicle = (
  customerId: string,
  vehicleId: string,
  body: object,
) =>
  api<CustomerVehicle>(
    `/api/v1/staff/customers/${customerId}/vehicles/${vehicleId}`,
    json("PATCH", body),
  );
export const deleteManagerCustomerVehicle = (
  customerId: string,
  vehicleId: string,
) =>
  api<void>(`/api/v1/staff/customers/${customerId}/vehicles/${vehicleId}`, {
    method: "DELETE",
  });
export const adjustManagerCustomerLoyalty = (
  customerId: string,
  body: object,
) =>
  api<LoyaltySummary>(
    `/api/v1/staff/customers/${customerId}/loyalty/adjustments`,
    json("POST", body),
  );
export const getLoyaltySettings = () =>
  api<LoyaltySettings>("/api/v1/staff/loyalty/settings");
export const updateLoyaltySettings = (body: object) =>
  api<LoyaltySettings>("/api/v1/staff/loyalty/settings", json("PATCH", body));
export const getServiceOptions = async () =>
  (await api<{ services: ServiceOption[] }>("/api/v1/public/catalogue"))
    .services;
export const assignJob = (jobId: string, body: object) =>
  api<Job>(`/api/v1/staff/jobs/${jobId}/assignment`, json("PATCH", body));
export const getTeams = () => api<Team[]>("/api/v1/staff/teams");
export const getTeam = (id: string) =>
  api<TeamDetail>(`/api/v1/staff/teams/${id}`);
export const createTeam = (name: string) =>
  api<TeamDetail>("/api/v1/staff/teams", json("POST", { name }));
export const updateTeam = (id: string, body: object) =>
  api<TeamDetail>(`/api/v1/staff/teams/${id}`, json("PATCH", body));
export const updateTeamMembers = (id: string, staffIds: string[]) =>
  api<TeamDetail>(
    `/api/v1/staff/teams/${id}/members`,
    json("PUT", { staff_ids: staffIds }),
  );
export const getDashboard = (day = today()) =>
  api<Dashboard>(`/api/v1/staff/dashboard?day=${day}`);
export const getAttendance = (start = today(), end = today()) =>
  api<{ items: Attendance[] }>(
    `/api/v1/staff/attendance?start_date=${start}&end_date=${end}`,
  );
export const getAttendanceOverview = (day = today()) =>
  api<AttendanceOverview[]>(`/api/v1/staff/attendance/overview?day=${day}`);
export const clockAttendance = (action: "clock-in" | "clock-out") =>
  api<Attendance>(
    `/api/v1/staff/attendance/${action}`,
    json("POST", { client_timestamp: new Date().toISOString() }),
  );
export const getShifts = () => api<Shift[]>("/api/v1/staff/shifts");
export const getShiftAssignments = (start = today(), end = today()) =>
  api<ShiftAssignment[]>(
    `/api/v1/staff/shift-assignments?start_date=${start}&end_date=${end}`,
  );
export const createShift = (body: object) =>
  api<Shift>("/api/v1/staff/shifts", json("POST", body));
export const assignShift = (body: object) =>
  api<ShiftAssignment>("/api/v1/staff/shift-assignments", json("PUT", body));
export const getLeave = (status?: string) =>
  api<Leave[]>(`/api/v1/staff/leave${status ? `?status=${status}` : ""}`);
export const requestLeave = (body: object) =>
  api<Leave>("/api/v1/staff/leave", json("POST", body));
export const reviewLeave = (id: string, decision: "approved" | "rejected") =>
  api<Leave>(`/api/v1/staff/leave/${id}/review`, json("POST", { decision }));
export const getReport = (start: string, end: string) =>
  api<ReportV2>(`/api/v1/staff/reports/v2?start_date=${start}&end_date=${end}`);
export const getCancellations = () =>
  api<Cancellation[]>("/api/v1/staff/cancellations");
export const reviewCancellation = (
  id: string,
  decision: "approved" | "rejected",
  clientEventId: string,
) =>
  api<Cancellation>(
    `/api/v1/staff/cancellations/${id}/review`,
    json("POST", { decision, client_event_id: clientEventId }),
  );
export async function getAvailability(
  date: string,
  vehicleCount: number,
  signal?: AbortSignal,
) {
  return api<{
    required_slot_count: number;
    slots: AvailabilitySlot[];
  }>(
    `/api/v1/public/availability?date=${date}&vehicle_count=${vehicleCount}`,
    { signal },
    undefined,
    AVAILABILITY_TIMEOUT_MS,
  );
}
export const createHold = (
  date: string,
  startTime: string,
  vehicleCount: number,
  resourceId?: string,
) =>
  api<{ hold_token: string; required_slot_count: number }>(
    "/api/v1/public/holds",
    json("POST", {
      date,
      start_time: startTime,
      vehicle_count: vehicleCount,
      ...(resourceId ? { resource_id: resourceId } : {}),
    }),
  );
export const rescheduleJob = (bookingId: string, body: object) =>
  api<Job>(
    `/api/v1/staff/bookings/${bookingId}/reschedule`,
    json("POST", body),
  );
