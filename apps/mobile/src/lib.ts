import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { createClient, type Session } from "@supabase/supabase-js";
import "react-native-url-polyfill/auto";
import type { Role } from "./capabilities";

const apiUrl = (process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
  process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "",
  {
    auth: {
      storage: { getItem: SecureStore.getItemAsync, setItem: SecureStore.setItemAsync, removeItem: SecureStore.deleteItemAsync },
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  },
);

export type { Role } from "./capabilities";
export type StaffContext = { staff_id: string; business_id: string; business_name: string; role: Role; timezone: string; display_name: string; username: string; phone: string | null };
export type TeamRef = { id: string; name: string };
export type Profile = { id: string; display_name: string; username: string; phone: string | null; role: Role; is_active: boolean; teams: TeamRef[] };
export type Job = { id: string; booking_id: string; booking_reference: string; assigned_staff_id: string | null; assigned_staff_name: string | null; assigned_team_id: string | null; assigned_team_name: string | null; status: string; scheduled_start: string; scheduled_end: string; en_route_at: string | null; estimated_arrival_at: string | null; started_at: string | null; completed_at: string | null; customer_name: string; customer_phone: string; written_address: string; location_url: string; latitude: number | null; longitude: number | null; location_instructions: string | null; payment_status: string; payment_method: string | null; total_amount_minor: number; currency_code: string; vehicles: { make: string; model: string; year: number | null; vehicle_type: string; colour: string | null; plate_number: string | null; notes: string | null; service_name: string; amount_minor: number }[] };
export type Team = { id: string; name: string; is_active: boolean; member_count: number; jobs_today: number; active_job_reference: string | null; active_job_status: string | null };
export type TeamDetail = Team & { members: Profile[]; jobs: Job[] };
export type Attendance = { id: string; staff_id: string; staff_name: string; clock_in_at: string; clock_out_at: string | null; worked_minutes: number; late_minutes: number; status: string };
export type Shift = { id: string; name: string; start_time: string; end_time: string; is_active: boolean };
export type ShiftAssignment = { id: string; staff_id: string; staff_name: string; shift_id: string; shift_name: string; work_date: string; start_time: string; end_time: string; team_id: string | null; team_name: string | null };
export type Leave = { id: string; staff_id: string; staff_name: string; start_date: string; end_date: string; reason: string; status: string; reviewed_at: string | null; review_note: string | null };
export type Report = { start_date: string; end_date: string; bookings: number; completed_washes: number; booked_sales_minor: number; collected_revenue_minor: number; outstanding_minor: number; average_booking_value_minor: number; currency_code: string };
export type ReportPoint = { date: string; booked_sales_minor: number; collected_revenue_minor: number; jobs: number; completed: number; cancelled: number };
export type Performance = { id: string; name: string; hours_worked: number; late_arrivals: number; jobs_completed: number; average_wash_minutes: number; jobs_per_worked_hour: number; job_value_handled_minor: number };
export type ReportV2 = { summary: Report; series: ReportPoint[]; staff_performance: Performance[] };
export type Dashboard = { date: string; currency_code: string; metrics: { key: string; label: string; value: number }[]; attention: { kind: string; count: number; label: string }[]; active_jobs: Job[] };
export type Cancellation = { id: string; booking_id: string; booking_reference: string; customer_name: string; reason: string | null; requested_at: string; scheduled_start: string; payment_status: string; status: string };
export type AvailabilitySlot = { time: string; starts_at: string; ends_at: string; available: boolean; required_slot_count: number; resources: { resource_id: string; resource_name: string }[]; unavailable_reason: string | null };

async function token(session?: Session | null): Promise<string | undefined> { return session?.access_token ?? (await supabase.auth.getSession()).data.session?.access_token; }
export async function api<T>(path: string, init?: RequestInit, session?: Session | null): Promise<T> { const headers = new Headers(init?.headers); const access = await token(session); if (access) headers.set("Authorization", `Bearer ${access}`); if (init?.body) headers.set("Content-Type", "application/json"); let response: Response; try { response = await fetch(`${apiUrl}${path}`, { ...init, headers }); } catch { throw new Error("OFFLINE"); } if (!response.ok) { const body = await response.json().catch(() => ({})) as { code?: string; detail?: { code?: string } }; throw new Error(body.code ?? body.detail?.code ?? "REQUEST_FAILED"); } if (response.status === 204) return undefined as T; return response.json() as Promise<T>; }
const json = (method: string, body: object): RequestInit => ({ method, body: JSON.stringify(body) });
const today = () => new Date().toISOString().slice(0, 10);

export const getContext = (session?: Session | null) => api<StaffContext>("/api/v1/staff/context", undefined, session);
export const getProfile = () => api<Profile>("/api/v1/staff/profile");
export const updateProfile = (body: object) => api<Profile>("/api/v1/staff/profile", json("PATCH", body));
export const getStaff = () => api<Profile[]>("/api/v1/staff/users");
export const createStaff = (body: object) => api<Profile>("/api/v1/staff/users", json("POST", body));
export const updateStaff = (id: string, body: object) => api<Profile>(`/api/v1/staff/users/${id}`, json("PATCH", body));
export const setTemporaryPassword = (id: string, temporaryPassword: string) => api<void>(`/api/v1/staff/users/${id}/temporary-password`, json("POST", { temporary_password: temporaryPassword }));
export async function getJobs(scope: "my" | "all", session?: Session | null) { const result = await api<{ jobs: Job[] }>(`/api/v1/staff/jobs?date=${today()}&scope=${scope}`, undefined, session); await AsyncStorage.setItem(`jobs:${scope}`, JSON.stringify({ at: new Date().toISOString(), jobs: result.jobs })); return result.jobs; }
export async function cachedJobs(scope: "my" | "all") { const value = await AsyncStorage.getItem(`jobs:${scope}`); return value ? JSON.parse(value) as { at: string; jobs: Job[] } : null; }
export const mutateJob = (jobId: string, action: "start-trip" | "start" | "complete" | "cash-payment", body: object) => api<Job>(`/api/v1/staff/jobs/${jobId}/${action}`, json("POST", body));
export const assignJob = (jobId: string, body: object) => api<Job>(`/api/v1/staff/jobs/${jobId}/assignment`, json("PATCH", body));
export const getTeams = () => api<Team[]>("/api/v1/staff/teams");
export const getTeam = (id: string) => api<TeamDetail>(`/api/v1/staff/teams/${id}`);
export const createTeam = (name: string) => api<TeamDetail>("/api/v1/staff/teams", json("POST", { name }));
export const updateTeam = (id: string, body: object) => api<TeamDetail>(`/api/v1/staff/teams/${id}`, json("PATCH", body));
export const updateTeamMembers = (id: string, staffIds: string[]) => api<TeamDetail>(`/api/v1/staff/teams/${id}/members`, json("PUT", { staff_ids: staffIds }));
export const getDashboard = () => api<Dashboard>(`/api/v1/staff/dashboard?day=${today()}`);
export const getAttendance = (start = today(), end = today()) => api<{ items: Attendance[] }>(`/api/v1/staff/attendance?start_date=${start}&end_date=${end}`);
export const clockAttendance = (action: "clock-in" | "clock-out") => api<Attendance>(`/api/v1/staff/attendance/${action}`, json("POST", { client_timestamp: new Date().toISOString() }));
export const getShifts = () => api<Shift[]>("/api/v1/staff/shifts");
export const getShiftAssignments = (start = today(), end = today()) => api<ShiftAssignment[]>(`/api/v1/staff/shift-assignments?start_date=${start}&end_date=${end}`);
export const createShift = (body: object) => api<Shift>("/api/v1/staff/shifts", json("POST", body));
export const assignShift = (body: object) => api<ShiftAssignment>("/api/v1/staff/shift-assignments", json("PUT", body));
export const getLeave = (status?: string) => api<Leave[]>(`/api/v1/staff/leave${status ? `?status=${status}` : ""}`);
export const requestLeave = (body: object) => api<Leave>("/api/v1/staff/leave", json("POST", body));
export const reviewLeave = (id: string, decision: "approved" | "rejected") => api<Leave>(`/api/v1/staff/leave/${id}/review`, json("POST", { decision }));
export const getReport = (start: string, end: string) => api<ReportV2>(`/api/v1/staff/reports/v2?start_date=${start}&end_date=${end}`);
export const getCancellations = () => api<Cancellation[]>("/api/v1/staff/cancellations");
export const reviewCancellation = (id: string, decision: "approved" | "rejected") => api<Cancellation>(`/api/v1/staff/cancellations/${id}/review`, json("POST", { decision, client_event_id: crypto.randomUUID() }));
export const getAvailability = (date: string, vehicleCount: number) => api<{ required_slot_count: number; slots: AvailabilitySlot[] }>(`/api/v1/public/availability?date=${date}&vehicle_count=${vehicleCount}`);
export const createHold = (date: string, startTime: string, vehicleCount: number, resourceId?: string) => api<{ hold_token: string; required_slot_count: number }>("/api/v1/public/holds", json("POST", { date, start_time: startTime, vehicle_count: vehicleCount, ...(resourceId ? { resource_id: resourceId } : {}) }));
export const rescheduleJob = (bookingId: string, body: object) => api<Job>(`/api/v1/staff/bookings/${bookingId}/reschedule`, json("POST", body));
export async function clearOperationalCache() { const keys = await AsyncStorage.getAllKeys(); await AsyncStorage.multiRemove(keys.filter((key) => key.startsWith("jobs:"))); }
