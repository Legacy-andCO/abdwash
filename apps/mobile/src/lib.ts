import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import { createClient, type Session } from "@supabase/supabase-js";
import "react-native-url-polyfill/auto";

const apiUrl = (process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const supabase = createClient(process.env.EXPO_PUBLIC_SUPABASE_URL ?? "", process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "", { auth: { storage: { getItem: SecureStore.getItemAsync, setItem: SecureStore.setItemAsync, removeItem: SecureStore.deleteItemAsync }, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } });
import type { Role } from "./capabilities";
export type { Role } from "./capabilities";
export type StaffContext = { staff_id: string; business_id: string; business_name: string; role: Role; timezone: string };
export type Job = { id: string; booking_id: string; booking_reference: string; assigned_staff_id: string | null; assigned_staff_name: string | null; status: string; scheduled_start: string; scheduled_end: string; en_route_at: string | null; estimated_arrival_at: string | null; started_at: string | null; completed_at: string | null; customer_name: string; customer_phone: string; written_address: string; location_url: string; latitude: number | null; longitude: number | null; location_instructions: string | null; payment_status: string; payment_method: string | null; total_amount_minor: number; currency_code: string; vehicles: { make: string; model: string; year: number | null; vehicle_type: string; colour: string | null; plate_number: string | null; notes: string | null; service_name: string; amount_minor: number }[] };
export type TeamMember = { id: string; display_name: string; role: string; assigned_jobs_today: number; current_job_reference: string | null; current_job_status: string | null };
export type Report = { start_date: string; end_date: string; bookings: number; completed_washes: number; booked_sales_minor: number; collected_revenue_minor: number; outstanding_minor: number; average_booking_value_minor: number; currency_code: string };
async function token(session?: Session | null) { return session?.access_token ?? (await supabase.auth.getSession()).data.session?.access_token; }
export async function api<T>(path: string, init?: RequestInit, session?: Session | null): Promise<T> { const headers = new Headers(init?.headers); const access = await token(session); if (access) headers.set("Authorization", `Bearer ${access}`); if (init?.body) headers.set("Content-Type", "application/json"); let response: Response; try { response = await fetch(`${apiUrl}${path}`, { ...init, headers }); } catch { throw new Error("OFFLINE"); } if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.code ?? body.detail?.code ?? "REQUEST_FAILED"); } return response.json() as Promise<T>; }
export const getContext = (session?: Session | null) => api<StaffContext>("/api/v1/staff/context", undefined, session);
export async function getJobs(scope: "my" | "all", session?: Session | null) { const result = await api<{ jobs: Job[] }>(`/api/v1/staff/jobs?date=${new Date().toISOString().slice(0, 10)}&scope=${scope}`, undefined, session); await AsyncStorage.setItem(`jobs:${scope}`, JSON.stringify({ at: new Date().toISOString(), jobs: result.jobs })); return result.jobs; }
export async function cachedJobs(scope: "my" | "all") { const value = await AsyncStorage.getItem(`jobs:${scope}`); return value ? JSON.parse(value) as { at: string; jobs: Job[] } : null; }
export const mutateJob = (jobId: string, action: "start-trip" | "start" | "complete" | "cash-payment", body: object) => api<Job>(`/api/v1/staff/jobs/${jobId}/${action}`, { method: "POST", body: JSON.stringify(body) });
export const getTeam = () => api<TeamMember[]>("/api/v1/staff/team");
export const getReport = (start: string, end: string) => api<Report>(`/api/v1/staff/reports/summary?start_date=${start}&end_date=${end}`);
export async function clearOperationalCache() { const keys = await AsyncStorage.getAllKeys(); await AsyncStorage.multiRemove(keys.filter((key) => key.startsWith("jobs:"))); }
