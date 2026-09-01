"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  LANGUAGE_STORAGE_KEY,
  appDirection,
  appLocale,
  preferredLanguage,
  translate,
  type AppLocale,
  type Language,
  type TranslationKey,
} from "@/lib/i18n";

type I18nContextValue = {
  language: Language;
  locale: AppLocale;
  direction: "rtl" | "ltr";
  setLanguage: (language: Language) => void;
  t: (key: TranslationKey, values?: Record<string, string | number>) => string;
};

const defaultValue: I18nContextValue = {
  language: "en",
  locale: "en-AE",
  direction: "ltr",
  setLanguage: () => undefined,
  t: (key, values) => translate("en", key, values),
};

const I18nContext = createContext<I18nContextValue>(defaultValue);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");
  const readyToPersist = useRef(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    const initial = preferredLanguage(stored ?? document.documentElement.lang ?? window.navigator.language);
    const timer = window.setTimeout(() => {
      readyToPersist.current = true;
      setLanguageState(initial);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = appDirection(language);
    if (!readyToPersist.current) return;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  }, [language]);

  const t = useCallback(
    (key: TranslationKey, values?: Record<string, string | number>) => translate(language, key, values),
    [language],
  );

  const value = useMemo<I18nContextValue>(() => ({
    language,
    locale: appLocale(language),
    direction: appDirection(language),
    setLanguage,
    t,
  }), [language, setLanguage, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { language, setLanguage, t } = useI18n();
  return (
    <div className={compact ? "language-switcher compact" : "language-switcher"} role="group" aria-label={t("language.label")}>
      <button type="button" lang="en" dir="ltr" aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button>
      <span aria-hidden="true">|</span>
      <button type="button" lang="ar" dir="rtl" aria-pressed={language === "ar"} onClick={() => setLanguage("ar")}>العربية</button>
    </div>
  );
}
