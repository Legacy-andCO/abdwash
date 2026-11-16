import { appLocale, interpolateMessage, translations, type Language } from "../../web/src/lib/i18n";
import { staffArabic } from "./staff-translations";

let language: Language = "en";
const listeners = new Set<() => void>();
const existing = new Map(Object.entries(translations.en).map(([key, value]) => [value, key as keyof typeof translations.en]));
const reverse = new Map(Object.entries(staffArabic).map(([en, ar]) => [ar, en]));
const normalized = new Map(Object.entries(staffArabic).map(([en, ar]) => [en.trim().toLowerCase(), ar]));
export const getStaffLanguage = () => language;
export const staffLocale = () => appLocale(language);
export const staffMoney = (minor: number, currency = "AED") => new Intl.NumberFormat(staffLocale(), { style: "currency", currency }).format(minor / 100);
export function setStaffLanguage(value: Language) {
  if (language === value) return;
  language = value;
  listeners.forEach(listener => listener());
}
export function subscribeStaffLanguage(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; }
export function t(message: string, values: Record<string, string | number | null | undefined> = {}): string {
  const source = reverse.get(message) ?? message;
  const common = existing.get(source);
  const value = language === "en" ? source : staffArabic[source] ?? normalized.get(source.trim().toLowerCase()) ?? (common ? translations.ar[common] : source);
  return interpolateMessage(value, Object.fromEntries(Object.entries(values).map(([key, item]) => [key, item ?? ""])));
}
